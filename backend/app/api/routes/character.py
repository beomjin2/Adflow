"""캐릭터 시트 — 대화로 8칸을 채우고, 다 찬 뒤에야 ComfyUI로 후보를 뽑는다.

흐름(기획 화이트보드 기준):

    대화로 시트를 채운다      가이드 순서: 외형 → 아웃핏 → 설명 → 능력 → 나이 → 성별 → 이름
        ↓ 7칸이 다 차면
    퍼스널 키워드 자동 제안    "이렇게 키워드를 정했어요" → 승인하면 시트 완성
        ↓ 완성을 알린다
    [그림 뽑기] 버튼이 열린다  ← 버튼을 눌러야만 생성이 시작된다. 대화가 저절로 돌리지 않는다
        ↓
    후보 3장 → 하나 고르기 → 확정

시트가 다 찬 뒤의 대화는 값을 바로 덮어쓰지 않는다. 수정 전/후를 confirm 카드로
보여주고 승인을 받는다. 승인하면 가이드 순서상 다음 칸도 고칠지 물어본다 —
사장님은 그 제안을 무시하고 시트에서 아무 칸이나 눌러 고쳐도 된다.

생성은 전부 백그라운드다(app/services/jobs.py). 요청은 즉시 돌아오고 칸이
status="generating"으로 생기며, 화면이 GET /api/character를 폴링해 채워진 그림을 받는다.

4방향 뽑기는 없다. 지금 워크플로우로는 같은 캐릭터를 네 각도로 만들 수 없어서
(고른 후보 이미지를 물리지 않고 텍스트에서 새 시드로 다시 뽑는 구조였다) 걷어냈다.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.services import character_sheet as sheet
from app.services import jobs, sheet_llm
from app.services.chat_ai import character_prompt, clothing_negative, new_pid, pending_candidates
from app.services.image_gen import eta_seconds, generate_images

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/character", tags=["character"])


def _get(db: Session) -> models.Character:
    char = db.get(models.Character, 1)
    if not char:
        raise HTTPException(404, "character row missing")
    return char


def _store(db: Session):
    """가게 정보. LLM이 이걸 못 보면 어느 가게에나 같은 캐릭터를 제안한다.

    없어도 된다 — sheet_llm이 "가게 정보를 모른다"고 프롬프트에 적고 넘어간다.
    """
    return db.get(models.Store, 1)


def _rank(field: str) -> int:
    """가이드 순서상 몇 번째 칸인가. 키워드는 순서 밖이라 맨 뒤로 보낸다."""
    return sheet.ORDER.index(field) if field in sheet.ORDER else len(sheet.ORDER)


def _label(field: str) -> str:
    return sheet.LABELS.get(field, sheet.KEYWORDS_LABEL)


def _fields_of(proposal: dict) -> set:
    """그 제안이 건드리는 칸들."""
    if proposal.get("kind") == "keywords":
        return {sheet.KEYWORDS_FIELD}
    changes = (proposal.get("payload") or {}).get("changes") or {}
    return set(changes) or {proposal.get("field", "")}


def _supersede(char, fields) -> None:
    """같은 칸을 다루던 **열린** 제안을 닫는다.

    안 닫으면 낡은 카드가 화면에 쌓인다. 배포된 서비스에서 외형 제안 카드 두 장이
    동시에 열린 채 남아 있었고(둘 다 '곰'이었다), 그동안 대화는 이미 다음 칸으로
    넘어가 있었다. 사장님은 어느 카드가 지금 것인지 알 수 없고, 옛 카드를 누르면
    한참 전에 지나간 값이 시트에 덮어써진다.
    """
    targets = {f for f in fields if f}
    if not targets:
        return
    _close_open(char, lambda proposal: bool(_fields_of(proposal) & targets))


def _close_open(char, match=None) -> None:
    """열려 있는 제안을 닫는다. match 를 안 주면 **전부** 닫는다.

    새 카드를 올리기 직전에 전부 닫는 이유 — 다른 칸 카드라도 남아 있으면 화면에
    승인 버튼이 여러 개 떠 있게 된다. 09-22 실측에서 외형·아웃핏·설명 카드가 **동시에
    세 장** 열려 있었고, 대화는 이미 한참 앞으로 가 있었다. 사장님이 그중 아무거나
    누르면 지나간 값이 지금 시트에 들어온다. 대화는 한 번에 하나를 묻는다.
    """
    pending = dict(char.pending or {})
    stale = [
        pid for pid, proposal in pending.items()
        if proposal.get("status") == "open" and (match is None or match(proposal))
    ]
    if not stale:
        return
    for pid in stale:
        pending[pid] = {**pending[pid], "status": "superseded"}
    char.pending = pending


def _shown_values(char, field: str) -> list:
    """그 칸에 대해 **이미 보여 드린** 값들. 같은 제안을 또 내지 않으려고 모은다.

    이게 없으면 "좀 더 자세히"에 **글자 하나 안 바뀐 값**이 다시 온다 — 09-22 실측.
    """
    seen = []
    for proposal in (char.pending or {}).values():
        if proposal.get("kind") != "field":
            continue
        value = ((proposal.get("payload") or {}).get("changes") or {}).get(field)
        if isinstance(value, str) and value.strip():
            seen.append(value.strip())
    current = (sheet.value_of(char, field) or "").strip()
    if current:
        seen.append(current)
    return seen


def _recorded_line(char, filling: dict) -> str:
    """무엇을 **어느 칸에** 적었는지 한 문장.

    _guide 는 다음에 할 말을 통째로 LLM 에게 맡기는데, 모델은 이 확인을 자주 빼먹고
    곧바로 다음 칸을 묻는다. 그러면 사장님은 자기 말이 어디에 적혔는지 모른다 —
    09-22 실측: 설명을 적어 두고도 "설명 안들어갔는데?"가 세 번 나왔다.
    이 문장만은 모델에 맡기지 않고 우리가 만든다.
    """
    parts = []
    for field in sorted(filling, key=_rank):
        value = (sheet.value_of(char, field) or "").strip()
        if not value:
            continue
        if len(value) > 40:
            value = value[:40] + "…"
        # 조사를 붙이지 않는다 — 값 끝이 받침으로 끝나느냐에 따라 '라고/이라고'가
        # 갈려서, 한쪽으로 고정하면 반은 틀린 말이 된다. 줄표로 잇는다.
        parts.append(f"'{_label(field)}'에 이렇게 적어뒀어요 — \"{value}\".")
    return " ".join(parts)


def _out(char, db: Session) -> schemas.CharacterOut:
    db.commit()
    db.refresh(char)
    return schemas.character_out(char, queue_depth=jobs.queue_depth())


def _say(messages: list, text: str) -> None:
    messages.append({"role": "ai", "kind": "text", "text": text})


def _fill_slots(field: str, indexes: list[int], prompt: str, count: int,
                negative_extra: str = "") -> None:
    """백그라운드 작업 본체 — 이미지를 뽑아 candidates의 해당 칸에 채운다.

    실패하면 status를 'failed'로 남긴다. 조용히 사라지면 사장님은 계속 기다리게 된다.
    """
    images = generate_images(prompt, count, negative_extra=negative_extra)

    def write(db: Session):
        char = db.get(models.Character, 1)
        if not char:
            return
        slots = list(getattr(char, field) or [])
        for slot_pos, index in enumerate(indexes):
            if not 0 <= index < len(slots):
                continue
            image = images[slot_pos] if slot_pos < len(images) else None
            slots[index] = {
                **slots[index],
                "image": image,
                "status": "done" if image else "failed",
            }
        setattr(char, field, slots)
        db.commit()

    jobs.with_session(write)


# ---------------------------------------------------------------- 시트 읽기/쓰기

@router.get("", response_model=schemas.CharacterOut)
def get_character(db: Session = Depends(get_db)):
    char = _get(db)
    return schemas.character_out(char, queue_depth=jobs.queue_depth())


@router.put("", response_model=schemas.CharacterOut)
def update_character(body: schemas.CharacterUpdate, db: Session = Depends(get_db)):
    """시트를 직접 고친다.

    대화와 달리 승인 단계를 두지 않는다 — 사장님이 그 칸에 직접 타이핑하고 있으므로
    '이렇게 바꿀까요?'를 다시 묻는 건 같은 말을 두 번 시키는 것이다. 승인 흐름은
    **AI가 제안할 때만** 쓴다.
    """
    char = _get(db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(char, field, value)
    return _out(char, db)


@router.post("/focus/{field}", response_model=schemas.CharacterOut)
def focus_field(field: str, db: Session = Depends(get_db)):
    """대화로 고칠 칸을 지정한다. 시트에서 어떤 칸을 눌렀을 때 호출된다."""
    char = _get(db)
    if field != sheet.KEYWORDS_FIELD and field not in sheet.ORDER:
        raise HTTPException(404, "그런 칸은 없어요")
    char.editing = field
    label = sheet.LABELS.get(field, sheet.KEYWORDS_LABEL)
    current = sheet.value_of(char, field)

    messages = list(char.messages or [])
    if current:
        _say(messages, f"'{label}'은(는) 지금 \"{current}\"예요. 어떻게 바꿀까요?")
    else:
        _say(messages, sheet.QUESTIONS.get(field, f"'{label}'을(를) 적어주세요."))
    char.messages = messages
    return _out(char, db)


# ---------------------------------------------------------------- 대화

@router.post("/chat", response_model=schemas.CharacterOut)
def chat(body: schemas.ChatIn, db: Session = Depends(get_db)):
    """사장님 말에서 **읽어낸 칸만** 채운다. 순서는 안내일 뿐 강제가 아니다.

    한 문장이 여러 칸을 건드리면 여러 칸이 한 번에 찬다("앞치마 두른 3살 곰이요"
    → 외형·아웃핏·나이). 묻고 있던 칸과 다른 칸을 말해도 그 칸에 들어간다.

    읽어낼 게 없으면 **시트를 건드리지 않는다**(`_handle_non_answer`). 예전에는
    물어본 칸에 원문을 통째로 넣어서 "몰라 좀 해봐"가 설명 칸에 적혔다.

    빈 칸을 채우는 동안은 승인을 받지 않는다 — 전/후가 없으니 보여줄 게 없다.
    예외가 하나 있다: 사장님이 "알아서 해줘"라고 해서 우리가 값을 **지어냈을 때**는
    승인 카드로 올린다. 시트가 다 찬 뒤의 수정도 덮어쓰기라 승인을 받는다.
    """
    char = _get(db)
    store = _store(db)
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "내용을 입력해주세요")

    messages = list(char.messages or [])
    messages.append({"role": "me", "kind": "text", "text": text})

    complete_before = sheet.is_complete(char)
    # 우리가 **실제로 물어본** 칸. 비어 있으면 아직 아무것도 묻지 않았다는 뜻이다.
    asked = char.editing
    # **첫 마디인가.** 아래에서 target 이 asked 를 덮어쓰기 때문에 여기서 미리 잡아 둔다.
    # 안 잡으면 "자 드가자"(= 시작하자) 한마디에 target='look' 이 붙어 곧바로 외형 제안
    # 카드가 뜬다(09-22 실측). 첫 마디는 부탁이 아니라 인사다 — 안내부터 한다.
    first_turn = not asked

    # LLM이 붙어 있으면 한 문장에서 여러 칸을 한 번에 읽고, **어느 칸 얘기인지**와
    # **대신 정해달라는 뜻인지**까지 같이 가려낸다.
    read = sheet_llm.understand(char, text, asked or sheet.next_field(char), store)
    fields = read.get("fields") or {}
    wants_help = read.get("wants_help", False)
    wants_all = read.get("wants_all", False)

    # **사장님이 가리킨 칸이 가이드 순서보다 우선이다.** 아웃핏을 묻는 중에 외형
    # 얘기를 하면 외형으로 옮겨간다. 예전에는 라우터가 "지금 묻는 칸"에 못 박아 둬서,
    # 앞 칸으로 돌아가려 해도 계속 원래 칸만 물었다.
    target = read.get("target") or ""
    if target and target != asked:
        char.editing = asked = target

    # **"나머지 알아서 만들어"는 한 칸 부탁이 아니다.** 남은 빈 칸을 한 카드에 모아 올린다.
    # 예전에는 이 말에도 칸 하나짜리 제안이 나가서, 사장님이 같은 말을 세 번 해야 했다
    # (09-22 실측: "나머지 알아서 만들어" -> 설명 하나만, 그것도 직전과 거의 같은 값).
    if wants_all and _offer_autofill(char, messages, store):
        char.messages = messages
        return _out(char, db)

    if not complete_before:
        # ---- 빈 칸 채우기 ----
        # 시트에 넣는 건 **LLM이 문장에서 실제로 읽어낸 것**뿐이다.
        #
        # 예전에는 못 읽으면 물어본 칸에 사장님 말을 통째로 넣었다(`{asked: text}`).
        # 그래서 "몰라 좀 해봐"가 설명 칸에, "모른다고"가 능력 칸에 그대로 적혔다.
        # 답이 아닌 말은 답이 아니다. 시트는 사장님이 **정한 것**만 담아야 한다.
        # **지금과 똑같은 값은 바꿀 내용이 아니다.** 추출 규칙 7(기존 값과 합쳐서 내기)
        # 때문에 그 칸의 기존 값이 그대로 되돌아오는 일이 잦은데, 그걸 덮어쓰기로 치면
        # "'외형'에는 이미 이렇게 적혀 있어요"로 끝나 대화가 막힌다(09-22 실측).
        # 걸러 두면 아래 _handle_non_answer 로 내려가 제안하거나 되묻는다.
        filling = {f: v for f, v in fields.items()
                   if (sheet.value_of(char, f) or "").strip() != (v or "").strip()}

        # **이미 값이 있는 칸은 조용히 갈아치우지 않고 승인 카드로 올린다.**
        # 빈 칸을 채우는 건 보여줄 전/후가 없어 바로 넣지만, 덮어쓰기는 사장님이 공들여
        # 적은 게 사라지는 일이라 한 번 보여주고 받는다.
        #
        # 예전에는 여기서 읽어낸 값을 **버리고** 제안으로 돌렸다. 그랬더니 사장님이
        # "소금빵을 진짜 잘 구워요" 처럼 값을 똑똑히 말해도 그 말이 통째로 버려졌다.
        overwriting = {f: v for f, v in filling.items() if sheet.value_of(char, f)}
        if overwriting:
            char.editing = max(overwriting, key=_rank)
            labels = ", ".join(f"'{_label(f)}'" for f in overwriting)
            _open_suggestion(char, messages, overwriting, phase="filling",
                             lead=f"{labels}을(를) 말씀하신 대로 바꿀까요?")
            char.messages = messages
            return _out(char, db)

        if not filling and asked and not sheet_llm.available():
            # LLM이 없을 때만 규칙 기반으로 되돌아간다 — 그때는 이것 말고 방법이 없다.
            filling = {asked: text}

        if filling:
            _record_and_continue(char, messages, filling, text, store)
        else:
            _handle_non_answer(char, messages, text, asked, store,
                               wants_help=wants_help, first_turn=first_turn)
    else:
        # ---- 다 찬 뒤의 수정 — 승인받고 반영한다 ----
        # 시트에서 칸을 눌러 '이 칸을 고치겠다'고 한 게 asked다. 그게 없어도
        # LLM이 어느 칸 얘기인지 읽어낼 수 있으면 대화만으로 고칠 수 있어야 한다.
        #
        # **지금과 똑같은 값은 '바꿀 내용'이 아니다.** "외형 다시 하고 싶어"처럼 고치겠다는
        # 말만 하면 추출 쪽이 지금 외형을 그대로 되돌려주는데, 그걸 수정으로 치면
        # "지금 시트와 같은 내용이에요"로 끝나고 칸이 열리지 않는다 — 배포 서버에서
        # 실제로 그랬다. 무의미한 값은 걷어내고 무엇을 고치려는 말인지 읽는 쪽으로 넘긴다.
        changes = {f: v for f, v in fields.items() if sheet.value_of(char, f) != v}
        if not changes and asked and sheet.value_of(char, asked) != text:
            changes = {asked: text}
        if changes:
            _open_suggestion(char, messages, changes)
        else:
            _handle_complete_chat(char, messages, text, store)

    char.messages = messages
    return _out(char, db)


def _record_and_continue(char, messages: list, filling: dict, text: str, store) -> None:
    """읽어낸 값을 시트에 적고, **무엇을 적었는지 알린 뒤** 다음 칸으로 간다.

    빈 칸을 채울 때는 승인을 안 받는다 — 전/후가 없어 보여 줄 게 없고, 사장님이 방금
    직접 한 말을 한 번 더 승인하게 만들 이유도 없다.
    """
    for field, value in filling.items():
        sheet.absorb(char, field, value)
    # 사장님이 그 칸을 직접 말해서 채웠다 — 같은 칸을 두고 띄워 둔 제안은 이미 지나간
    # 얘기다. 안 닫으면 옛 제안 카드가 화면에 남는다.
    _supersede(char, filling)
    # 적힌 줄을 눈으로 확인할 수 있게 **우리가** 앞에 붙인다(_recorded_line).
    recorded = _recorded_line(char, filling)

    following = sheet.next_field(char)
    if following:
        char.editing = following
        said = _guide(char, text, filling, following, store,
                      fallback=sheet.QUESTIONS[following])
        _say(messages, f"{recorded} {said}".strip())
    else:
        # 묻는 칸이 다 찼다 — 키워드를 뽑아 제안한다.
        char.editing = ""
        _say(messages, f"{recorded} 시트가 다 채워졌어요.".strip())
        _propose_keywords(char, messages, store)


def _handle_complete_chat(char, messages: list, text: str, store) -> None:
    """시트가 다 찬 뒤, 값이 안 읽힌 말에 답한다. **대화로도 고칠 수 있어야 한다.**

    예전에는 여기가 한 문장짜리였다 — "고치고 싶은 칸을 시트에서 눌러주세요". 그래서
    "외형 다시 하고 싶어"라고 말해도 아무 일도 일어나지 않았다. 대화로 만든 캐릭터를
    대화로는 못 고치는 상태였다. 이제 무엇을 고치려는 말인지 먼저 읽는다.
    """
    wanted = sheet_llm.detect_edit_target(char, text, store)
    intent = wanted.get("intent")

    if intent == "edit":
        field = wanted["field"]
        char.editing = field
        value = wanted.get("value")
        if value:
            # 어떻게 바꿀지까지 말했다 — 바로 승인 카드로 올린다.
            _open_suggestion(char, messages, {field: value})
            return
        # 고칠 칸만 정했다. 그 칸을 열고 지금 값을 보여준 뒤 다시 묻는다.
        current = sheet.value_of(char, field)
        _say(
            messages,
            f"'{_label(field)}'을(를) 다시 정해볼게요. 지금은 \"{current}\"로 적혀 있어요. "
            f"어떻게 바꿀까요? 정하기 어려우시면 '알아서 정해줘'라고 하셔도 돼요.",
        )
        return

    if intent == "regenerate":
        _say(
            messages,
            "그림을 다시 뽑으시려면 시트 아래 '다시 뽑기'를 눌러주세요 — 지금 시트 그대로 "
            f"3장을 새로 그립니다. 약 {eta_seconds(3)}초 걸려요.",
        )
        return

    if intent == "restart":
        _say(
            messages,
            "처음부터 다시 만드시려면 대화창 위의 '처음부터 다시'를 눌러주세요. "
            "시트와 대화가 전부 지워지고 외형부터 새로 시작해요.",
        )
        return

    _say(
        messages,
        "시트는 다 채워져 있어요. 어느 칸을 고칠지 말씀해주시면 거기부터 바꿀게요 — "
        "'외형 다시', '이름 바꿀래'처럼 말씀하셔도 되고, 시트에서 칸을 직접 눌러도 돼요.",
    )


def _handle_non_answer(char, messages: list, text: str, asked: str, store,
                       wants_help: bool = False, first_turn: bool = False) -> None:
    """시트에 넣을 내용이 없는 말에 답한다. **사장님 말이 시트에 적히는 일은 없다.**

    세 갈래다.
      - 아직 아무것도 안 물었다 → 말을 거는 첫 마디다. 시작 안내를 하고 첫 칸을 묻는다.
      - "몰라, 알아서 해줘" → 대신 정해서 **승인 카드로** 올린다. 지어낸 값이니
        시트에 바로 넣지 않는다 — 무엇을 지어냈는지 보고 사장님이 정한다.
      - 그 밖의 잡담 → 시트를 건드리지 않고, 막혔을 때 쓸 수 있는 길을 알려준다.
    """
    following = asked or sheet.next_field(char)
    if not following:
        _say(messages, "시트가 다 찼어요. 고치고 싶은 칸을 시트에서 눌러주세요.")
        return

    if first_turn:
        char.editing = following
        _say(messages, _guide(
            char, text, {}, following, store,
            fallback=(
                f"캐릭터를 같이 만들어볼게요. {sheet.QUESTIONS[following]}\n"
                "순서대로 안 하셔도 돼요 — 떠오르는 대로 말씀하시면 해당하는 칸에 적어둘게요."
            ),
        ))
        return

    # **사장님이 다른 칸 얘기를 하면 그 칸으로 옮긴다.** 묻고 있는 칸에 갇히면 안 된다 —
    # 아웃핏을 묻는 중에 "고양이 말고 다른 외형 추천해줘"라고 해도 계속 아웃핏만 물었고,
    # 심지어 외형 값("흰색 털에 긴 꼬리를 가진 강아지")을 아웃핏 칸에 제안했다.
    # 어느 칸인지 가르는 일은 LLM이 한다 — 여기서 키워드로 정하지 않는다.
    # **칸 판단은 언제나 한 번 더 묻는다.** understand()가 이미 target을 냈더라도
    # 건너뛰지 않는다 — 그게 틀렸을 때 되돌릴 길이 없어진다. 실제로 능력을 묻는 중에
    # "외형자체가 그게 아니고 너가 정해달라는거야"라고 했는데 능력에 갇혔다.
    # 이쪽은 "어느 칸 얘기인가" 하나만 보는 전문 판단이라 더 믿을 만하다.
    wanted = sheet_llm.detect_edit_target(char, text, store)
    if wanted.get("intent") == "edit" and wanted["field"] != following:
        following = wanted["field"]
        char.editing = following
        value = (wanted.get("value") or "").strip()
        # **지금과 같은 값은 수정이 아니다.** "능력채워"처럼 그 칸을 손봐 달라는 말에
        # 추출 쪽이 지금 값을 그대로 되돌려주는 일이 잦은데, 그걸 카드로 올리면
        # "'능력'에는 이미 이렇게 적혀 있어요"로 끝난다 — 부탁을 거절한 셈이다
        # (09-22 실측). 그런 값은 버리고 아래 제안 갈래로 내려간다.
        current = (sheet.value_of(char, following) or "").strip()
        if value and value != current:
            if current:
                _open_suggestion(char, messages, {following: value}, phase="filling")
            else:
                # 빈 칸이다. 사장님이 직접 말한 값이니 승인받을 게 없다 — 바로 적는다.
                # 여기에까지 카드를 띄우면 사장님은 자기가 한 말을 한 번 더 승인해야 한다
                # (09-22 실측: "돈개잘버는게 능력이야"가 빈 능력 칸에 카드로 올라왔다).
                _record_and_continue(char, messages, {following: value}, text, store)
            return

    # 🔴 **제안은 사장님이 부탁했을 때만 낸다.**
    # 예전에는 값이 안 읽히기만 하면 무조건 제안 카드를 띄웠다. 그래서 되묻는 말에도,
    # 잡담에도 승인 카드가 올라왔다 — 사장님 말로 "제안이 내가 원할 때 나와야 되는거고".
    # 부탁인지 아닌지는 understand() 가 이미 뜻으로 가려 놓았다(wants_help).
    if wants_help:
        # 이미 보여 드린 값과 같은 건 안 받는다 — 같은 제안이 두 번 오면 대화가 멈춘다.
        proposal = sheet_llm.propose_field(
            char, following, text, store,
            avoid=_shown_values(char, following), asked_for=True)
        if proposal:
            char.editing = following
            # 물어보신 말에 먼저 답하고, 그 답의 결론을 카드로 올린다. 카드만 띄우면
            # "왜 앞치마인가"가 없어서 사장님은 근거 없이 정해진 값으로 읽는다.
            # 무엇을 보고 정했는지(basis)도 카드에 같이 싣는다.
            _open_suggestion(
                char, messages, {following: proposal["value"]}, phase="filling",
                lead=proposal.get("say") or sheet_llm.reply(char, text, {}, following, store),
                basis=proposal.get("basis"), why=proposal.get("why"),
            )
            return

    # 시트에 넣을 건 없지만 **할 말은 있다.** 질문이었을 수도 있고 고민이었을 수도 있다.
    # 여기서 정해진 문장만 돌려주면 "무슨 말을 해도 같은 소리를 한다"가 된다.
    label = sheet.LABELS[following]
    char.editing = following
    current = (sheet.value_of(char, following) or "").strip()
    _say(messages, _guide(
        char, text, {}, following, store,
        fallback=(
            f"'{label}'에는 지금 \"{current}\"라고 적혀 있어요. 어떻게 바꿀까요?"
            if current else
            f"방금 말씀은 시트에 넣지 않았어요. '{label}'은(는) 편하게 적어주셔도 되고, "
            "정하기 어려우시면 '알아서 정해줘'라고 하시면 제가 하나 제안해 드릴게요."
        ),
    ))


def _guide(char, text: str, filled: dict, ask_field: str, store, fallback: str) -> str:
    """사장님 말에 대답하고 다음 칸을 묻는 한 문단. LLM이 못 하면 정해진 문장으로.

    정해진 문장(`fallback`)은 누구에게나 똑같다. 그래서 "캐릭터화하면 뭘 하면
    좋을까"라는 질문에도 "무엇을 입고 있으면 좋을까요?"로 답했다. 대화를 하려면
    **방금 한 말을 읽고 답해야** 한다. 실패하면 조용히 정해진 문장으로 돌아간다 —
    대화가 멈추는 것보다 딱딱한 게 낫다.
    """
    return sheet_llm.reply(char, text, filled, ask_field, store) or fallback


def _propose_keywords(char, messages: list, store=None) -> None:
    """퍼스널 키워드를 자동으로 뽑아 승인 카드로 올린다.

    뽑을 말이 없으면 지어내지 않고 사장님에게 직접 묻는다. 그럴듯한 형용사를 채워
    넣으면 그건 사장님이 정한 적 없는 성격이 된다.
    """
    # 이미 채워져 있으면 다시 제안하지 않는다. "전부 만들기"가 키워드까지 한 번에
    # 채우는데, 그 뒤에 또 물으면 방금 정한 걸 되묻는 꼴이 된다.
    if sheet.value_of(char, sheet.KEYWORDS_FIELD):
        _announce_ready(char, messages)
        return

    # LLM이 붙어 있으면 문장의 뜻을 보고 고르고, 어느 칸에서 뽑았는지도 같이 내놓는다.
    # 없으면 사장님이 쓴 형용사를 정규식으로 집어낸다 — 그때 근거는 "직접 쓰신 말"이다.
    proposal = sheet_llm.suggest_keywords(char, store=store)
    guessed = proposal.get("keywords") if proposal else sheet.derive_keywords(char)
    if not guessed:
        char.editing = sheet.KEYWORDS_FIELD
        _say(
            messages,
            "마지막으로 퍼스널 키워드만 남았어요. 적어주신 글에서 뽑아낼 말을 못 찾았어요 — "
            "이 캐릭터를 한마디로 말하면 어떤 느낌인가요? 쉼표로 여러 개 적으셔도 돼요.",
        )
        return

    proposed = ", ".join(guessed)
    _supersede(char, [sheet.KEYWORDS_FIELD])
    pending = dict(char.pending or {})
    pid = new_pid()
    pending[pid] = {
        "kind": "keywords",
        "field": sheet.KEYWORDS_FIELD,
        "diffs": sheet.diff_for(char, sheet.KEYWORDS_FIELD, proposed),
        "payload": {"keywords": guessed},
        "basis": (proposal.get("basis") if proposal else []) or _fallback_basis(char, guessed),
        "why": (proposal.get("why") if proposal else "")
               or ("적어주신 말에서 성격을 나타내는 말만 골라냈어요." if guessed else ""),
        "status": "open",
    }
    char.pending = pending
    _say(
        messages,
        f"적어주신 내용에서 퍼스널 키워드를 이렇게 정했어요 — {proposed}. "
        "이대로 둘까요? 마음에 안 드시면 직접 적어주셔도 돼요.",
    )
    messages.append({"role": "ai", "kind": "confirm", "pid": pid})


def _fallback_basis(char, picked: list) -> list:
    """LLM 없이 정규식으로 키워드를 뽑았을 때의 근거.

    `derive_keywords()`가 설명 → 능력 → 외형 순으로 훑으므로, 뽑힌 말의 뿌리가 남아
    있는 칸을 근거로 보여준다. 못 찾으면 빈 목록 — 근거를 지어내지 않는다.
    """
    basis = []
    for field in ("desc", "abilities", "look"):
        value = sheet.value_of(char, field)
        # '느긋한'은 '느긋하고'에서 나온 것이다. 어간(앞 두 글자)이 남아 있으면 그 칸이 출처다.
        if value and any(word[:2] in value for word in picked if len(word) >= 2):
            basis.append({"label": sheet.LABELS[field], "quote": value})
    return basis[:3]


def _open_suggestion(char, messages: list, changes: dict, phase: str = "editing",
                     lead: str = "", basis=None, why: str = "") -> None:
    """수정 제안을 승인 대기로 올린다. 한 문장이 여러 칸을 건드리면 한 카드에 모아 보여준다.

    phase는 승인 뒤 어디로 이어갈지를 정한다.
      - "editing"  — 다 찬 시트를 고치는 중. 가이드 순서상 다음 칸을 이어서 물어본다.
      - "filling"  — 아직 빈 칸을 채우는 중. 가이드가 아니라 **남은 빈 칸**으로 이어간다.
    """
    # 지금과 같은 값은 뺀다 — "바꿀까요?"라고 물으면서 같은 걸 보여주면 안 된다.
    # 퍼스널 키워드도 대화로 고칠 수 있어야 한다. ORDER에는 없지만 absorb·diff_for는
    # 그 칸을 다룰 줄 안다 — 예전에는 여기서 걸러져 "지금 시트와 같은 내용이에요"가 나왔다.
    editable = set(sheet.ORDER) | {sheet.KEYWORDS_FIELD}
    real = {f: v for f, v in changes.items() if f in editable and sheet.value_of(char, f) != v}
    if not real:
        # 🔴 "그대로 둘게요"로 끝내면 막다른 길이다. 사장님이 "설명 안 들어갔는데?"
        # 라고 한 건 **그 칸이 비었다고 믿고 있다**는 뜻인데, 같은 말을 반복하면
        # 믿음이 안 바뀐다(09-22 실측: 같은 답이 세 번 나오고 대화가 멈췄다).
        # 무엇이 적혀 있는지 보여준다 — 그래야 "아 들어가 있었네" 아니면
        # "그게 아니라 이렇게" 로 넘어간다.
        same = [f for f in changes if f in editable]
        if same:
            field = same[0]
            value = (sheet.value_of(char, field) or "").strip()
            label = sheet.LABELS.get(field, field)
            if value:
                _say(messages, f"'{label}'에는 이미 이렇게 적혀 있어요 — \"{value}\". "
                               "다르게 바꾸시려면 어떻게 할지 말씀해 주세요.")
                return
        _say(messages, "지금 시트와 같은 내용이에요. 그대로 둘게요.")
        return

    # 열린 카드를 **전부** 닫는다. 같은 칸만 닫으면 다른 칸 카드가 그대로 남아,
    # 화면에 승인 버튼이 여러 개 떠 있게 된다(_close_open 주석 참고).
    _close_open(char)

    diffs = []
    for field, value in real.items():
        diffs.extend(sheet.diff_for(char, field, value))

    pending = dict(char.pending or {})
    pid = new_pid()
    pending[pid] = {
        "kind": "field",
        "phase": phase,
        # 승인 뒤 가이드 제안의 기준점. 여러 칸이면 가이드 순서상 가장 뒤쪽을 기준으로 삼는다.
        "field": max(real, key=_rank),
        # 빈 칸을 채우는 게 아니라 **이미 있던 값을 고치는 것**인가. 승인 뒤에 어디로
        # 갈지를 이걸로 가른다 — 고친 거면 그 칸에 머물러야 한다.
        "redo": any(sheet.value_of(char, f) for f in real),
        "diffs": diffs,
        "payload": {"changes": real},
        # 우리가 대신 정해준 값일 때만 근거가 붙는다. 사장님이 직접 말한 수정에는
        # 근거를 달지 않는다 — 사장님이 쓴 말이 곧 근거라 되돌려줄 이유가 없다.
        "basis": basis or [],
        "why": why or "",
        "status": "open",
    }
    char.pending = pending
    labels = ", ".join(f"'{_label(f)}'" for f in real)
    if lead:
        # 사장님이 물어보신 말에 대한 실제 대답이다. "이렇게 하면 어떨까요?"만
        # 던지면 왜 그 값인지가 없어서, 카드가 있어도 근거 없는 제안으로 읽힌다.
        _say(messages, lead)
    elif phase == "filling":
        _say(messages, f"그럼 {labels}은(는) 이렇게 하면 어떨까요?")
    else:
        _say(messages, f"{labels}을(를) 이렇게 바꿀까요?")
    messages.append({"role": "ai", "kind": "confirm", "pid": pid})


def _offer_autofill(char, messages: list, store) -> bool:
    """남은 빈 칸을 **한 카드에 모아** 제안한다. 올렸으면 True.

    버튼('알아서 전부 만들기')과 대화("나머지 알아서 만들어")가 같은 길을 쓴다 —
    사장님에게는 같은 부탁인데 눌렀을 때만 되는 건 말이 안 된다.
    빈 칸이 없거나 LLM 이 못 만들면 False 를 돌려준다. 그때는 부르는 쪽이 이어간다.
    """
    made = sheet_llm.autofill(char, store)
    if not made or not made.get("fields"):
        return False
    char.editing = ""
    _open_suggestion(
        char, messages, made["fields"], phase="filling",
        lead=made.get("say") or "남은 칸을 이렇게 채워봤어요. 이대로 할까요?",
        basis=made.get("basis"), why=made.get("why"),
    )
    return True


@router.post("/autofill", response_model=schemas.CharacterOut)
def autofill_sheet(db: Session = Depends(get_db)):
    """빈 칸을 한 번에 채워 **승인 카드 한 장**으로 올린다.

    사장님이 "알아서 전부 만들기"를 눌렀을 때 온다. 대화로 한 칸씩 가는 게 번거로운
    분을 위한 지름길이다.

    **이미 적어 둔 칸은 건드리지 않는다** — 빈 칸만 채운다. 그래서 반쯤 채우다 눌러도
    앞서 정한 게 그대로 남는다.

    바로 시트에 넣지 않고 카드로 올리는 건 다른 제안과 같은 이유다: 우리가 지어낸
    값이니 무엇을 지어냈는지 보고 사장님이 정한다. 한 번에 승인된다.
    """
    char = _get(db)
    store = _store(db)

    if sheet.ready_to_generate(char):
        raise HTTPException(400, "시트가 이미 다 채워져 있어요. 고치고 싶은 칸을 말씀해주세요")

    messages = list(char.messages or [])
    messages.append({"role": "me", "kind": "text", "text": "알아서 전부 만들어줘"})
    if not _offer_autofill(char, messages, store):
        raise HTTPException(503, "지금은 만들어 드리지 못했어요. 잠시 뒤 다시 눌러주세요")
    char.messages = messages
    return _out(char, db)


@router.post("/suggestions/{pid}/accept", response_model=schemas.CharacterOut)
def accept_suggestion(pid: str, db: Session = Depends(get_db)):
    """제안을 반영하고, 가이드 순서상 다음 칸도 고칠지 물어본다."""
    char = _get(db)
    store = _store(db)
    pending = dict(char.pending or {})
    proposal = pending.get(pid)
    if not proposal:
        raise HTTPException(404, "그 제안을 찾을 수 없어요")
    if proposal.get("status") != "open":
        raise HTTPException(400, "이미 처리된 제안이에요")

    pending[pid] = {**proposal, "status": "applied"}
    char.pending = pending
    # 같은 칸을 두고 함께 열려 있던 다른 제안은 이제 지나간 것이다. 안 닫으면 방금
    # 정한 값을 옛 카드가 덮어쓸 수 있다.
    _supersede(char, _fields_of(proposal))
    messages = list(char.messages or [])

    if proposal["kind"] == "keywords":
        char.keywords = proposal["payload"]["keywords"]
        char.editing = ""
        _say(messages, "키워드를 그렇게 정했어요.")
        _announce_ready(char, messages)
    else:
        changes = proposal["payload"]["changes"]
        for field, value in changes.items():
            sheet.absorb(char, field, value)
        label = ", ".join(_label(f) for f in changes)

        if proposal.get("phase") == "filling":
            # **고친 것이면 그 칸에 머문다.** 사장님이 "외형 다른거"라고 해서 고쳐 놓고
            # 곧바로 다음 칸을 물으면, 방금 고친 게 마음에 드는지 말할 틈이 없다.
            # 실제로 외형을 고친 직후 설명을 물어 버려서 사장님이 같은 말을 반복했다.
            if proposal.get("redo"):
                stay = proposal["field"]
                char.editing = stay
                following = sheet.next_field(char)
                nxt = f" 이대로 괜찮으시면 다음은 '{_label(following)}'이에요." if following else ""
                _say(messages, f"{label} 이렇게 바꿨어요. 더 고칠 게 있으면 말씀해주세요.{nxt}")
                char.messages = messages
                return _out(char, db)

            # 빈 칸을 대신 정해준 제안이었다. 가이드가 아니라 **남은 빈 칸**으로 이어간다.
            following = sheet.next_field(char)
            if following:
                char.editing = following
                _say(messages, f"{label} 그렇게 적어뒀어요. {sheet.QUESTIONS[following]}")
            else:
                char.editing = ""
                _say(messages, f"{label}까지 적어뒀어요. 시트가 다 채워졌어요.")
                _propose_keywords(char, messages, store)
        else:
            _note_stale_art(char, messages, changes)
            # 가이드 순서상 다음 칸. 여러 칸을 한 번에 바꿨으면 가장 뒤쪽 칸 기준이다.
            following = sheet.next_in_guide(proposal["field"])
            if following:
                char.editing = following
                _say(
                    messages,
                    f"{label} 바꿨어요. 가이드 순서대로면 다음은 '{sheet.LABELS[following]}'이에요 — "
                    f"여기도 고칠까요? 다른 칸을 고치고 싶으시면 시트에서 그 칸을 눌러주세요.",
                )
            else:
                char.editing = ""
                _say(messages, f"{label} 바꿨어요. 더 고칠 칸이 있으면 시트에서 눌러주세요.")

    char.messages = messages
    return _out(char, db)


@router.post("/suggestions/{pid}/decline", response_model=schemas.CharacterOut)
def decline_suggestion(pid: str, db: Session = Depends(get_db)):
    char = _get(db)
    pending = dict(char.pending or {})
    proposal = pending.get(pid)
    if not proposal or proposal.get("status") != "open":
        raise HTTPException(404, "처리할 수 있는 제안이 아니에요")

    pending[pid] = {**proposal, "status": "declined"}
    char.pending = pending
    messages = list(char.messages or [])

    if proposal["kind"] == "keywords":
        # 키워드가 비면 시트가 미완성이라 생성이 잠긴 채로 남는다. 직접 받아야 한다.
        char.editing = sheet.KEYWORDS_FIELD
        _say(messages, "그럼 퍼스널 키워드를 직접 적어주세요. 쉼표로 여러 개 적으셔도 돼요.")
    elif proposal.get("phase") == "filling":
        # 대신 정해준 게 마음에 안 든 것이다. 그 칸은 여전히 비어 있으니 다시 묻는다.
        field = proposal["field"]
        char.editing = field
        _say(
            messages,
            f"그럼 '{_label(field)}'은(는) 사장님이 정해주세요. {sheet.QUESTIONS.get(field, '')}",
        )
    else:
        _say(messages, "그대로 둘게요. 어떻게 바꾸면 좋을지 다시 적어주세요.")

    char.messages = messages
    return _out(char, db)


def _note_stale_art(char, messages: list, changed: dict) -> None:
    """그림에 쓰이는 칸이 바뀌었는데 이미 뽑아 둔 그림이 있으면 그 사실을 알린다.

    시트만 바뀌고 그림은 그대로라서, 사장님은 "외형을 바꿨는데 아무것도 안 변했다"로
    읽는다. 여기서 그림을 저절로 다시 뽑지는 않는다 — 생성은 사장님이 버튼을 눌렀을
    때만 시작한다는 규칙이 있고, 한 장에 1분씩 걸리기 때문이다.
    """
    if not (char.candidates or []):
        return
    if not any(field in sheet.IMAGE_FIELDS for field in changed):
        return
    _say(
        messages,
        "여기까지는 시트만 바뀐 거예요 — 지금 보이는 그림은 바꾸기 전 캐릭터예요. "
        "아래 '다시 뽑기'를 누르면 바뀐 시트대로 새로 그려드릴게요.",
    )


def _announce_ready(char, messages: list) -> None:
    """시트가 다 찼다는 사실을 알린다. 생성은 여기서 시작하지 않는다 — 버튼이 한다."""
    if sheet.ready_to_generate(char):
        _say(
            messages,
            "캐릭터 시트가 완성됐어요. 이제 아래 '그림 뽑기'를 누르시면 후보 3장을 그려드릴게요 — "
            f"약 {eta_seconds(3)}초 걸려요.",
        )
    else:
        left = ", ".join(
            sheet.KEYWORDS_LABEL if f == sheet.KEYWORDS_FIELD else sheet.LABELS[f]
            for f in sheet.missing_all(char)
        )
        _say(messages, f"아직 {left}이(가) 비어 있어요.")


# ---------------------------------------------------------------- 그림

def _require_full_sheet(char) -> None:
    """시트가 다 차지 않으면 생성을 열지 않는다."""
    if sheet.ready_to_generate(char):
        return
    left = ", ".join(
        sheet.KEYWORDS_LABEL if f == sheet.KEYWORDS_FIELD else sheet.LABELS[f]
        for f in sheet.missing_all(char)
    )
    raise HTTPException(400, f"캐릭터 시트를 먼저 다 채워주세요. 남은 칸: {left}")


def _freeze_cands(messages: list, cands: list) -> None:
    """대화에 남아 있는 후보 카드에 **그때 그린 그림**을 박아 둔다.

    후보 카드는 원래 살아 있는 목록(char.candidates)을 가리키기만 한다("ref": "cands").
    카드가 한 장일 때는 맞는 얘기였는데, 다시 뽑기를 누르면 **대화에 쌓인 지난 카드까지
    전부** 그 목록을 비춘다 — 이미 다 그려 둔 위쪽 그림 석 장이 한꺼번에 "그리는 중"으로
    바뀐다(09-22 사장님 화면). 다 끝난 일이 진행 중인 것처럼 보이고, 그동안 그림은 사라진다.

    그래서 새로 뽑기 **직전에** 지난 카드에 그때의 그림을 박는다. 그림 파일은 안 지우니
    계속 보인다. 한 번 얼린 카드는 다시 안 건드린다.
    """
    done = [c for c in cands if isinstance(c, dict) and c.get("image")]
    for i, m in enumerate(messages):
        if m.get("kind") == "cands" and "items" not in m:
            messages[i] = {**m, "items": done}


@router.post("/candidates", response_model=schemas.CharacterOut)
def gen_candidates(db: Session = Depends(get_db)):
    """후보 3장을 뽑는다. **사장님이 버튼을 눌렀을 때만** 여기 온다."""
    char = _get(db)
    _require_full_sheet(char)

    messages = list(char.messages or [])
    # 지난 카드를 먼저 얼린다 — char.candidates 를 갈아치우기 전이어야 그림이 남는다.
    _freeze_cands(messages, char.candidates or [])

    char.candidates = pending_candidates(3)
    char.selected_index = -1
    _say(messages, f"시트대로 3장 그려볼게요. 약 {eta_seconds(3)}초 걸려요 — 창을 닫으셔도 서버에서 계속 그립니다.")
    messages.append({"role": "ai", "kind": "cands", "ref": "cands"})
    char.messages = messages
    db.commit()

    prompt = character_prompt(char)
    jobs.submit(_fill_slots, "candidates", [0, 1, 2], prompt, 3, clothing_negative(prompt))

    db.refresh(char)
    return schemas.character_out(char, queue_depth=jobs.queue_depth())


@router.post("/candidates/{index}/reroll", response_model=schemas.CharacterOut)
def reroll_candidate(index: int, db: Session = Depends(get_db)):
    """후보 한 칸만 다시 뽑는다."""
    char = _get(db)
    _require_full_sheet(char)

    cands = list(char.candidates or [])
    if not 0 <= index < len(cands):
        raise HTTPException(404, "candidate index out of range")
    cands[index] = {**cands[index], "image": None, "status": "generating"}
    char.candidates = cands
    db.commit()

    prompt = character_prompt(char, f"variation {index + 1}")
    jobs.submit(_fill_slots, "candidates", [index], prompt, 1, clothing_negative(prompt))

    db.refresh(char)
    return schemas.character_out(char, queue_depth=jobs.queue_depth())


@router.post("/select/{index}", response_model=schemas.CharacterOut)
def select_candidate(index: int, db: Session = Depends(get_db)):
    """후보를 고른다. 고른 그림이 곧 이 캐릭터의 그림이다."""
    char = _get(db)
    cands = char.candidates or []
    if not 0 <= index < len(cands):
        raise HTTPException(404, "candidate index out of range")
    if cands[index].get("status") == "generating":
        raise HTTPException(400, "아직 그려지는 중이에요. 그림이 나온 뒤에 골라주세요")
    if not cands[index].get("image"):
        raise HTTPException(400, "이 후보는 그리기에 실패했어요. 다시 뽑은 뒤에 골라주세요")

    char.selected_index = index
    messages = list(char.messages or [])
    messages.append({"role": "me", "kind": "text", "text": f"{index + 1}번으로 할게요"})
    _say(messages, f"{index + 1}번으로 정했어요. 아래 '이 캐릭터로 확정'을 누르면 시트가 완성됩니다.")
    char.messages = messages
    return _out(char, db)


# ---------------------------------------------------------------- 마무리

@router.post("/load-previous", response_model=schemas.CharacterOut)
def load_previous(db: Session = Depends(get_db)):
    """전에 확정한 캐릭터를 다시 쓴다. 확정한 게 없으면 불러올 것도 없다."""
    char = _get(db)
    if not char.confirmed:
        raise HTTPException(400, "전에 만들어 확정한 캐릭터가 없어요. 새로 만들어주세요")
    messages = list(char.messages or [])
    _say(messages, "전에 확정한 캐릭터를 그대로 쓸게요.")
    char.messages = messages
    return _out(char, db)


@router.post("/reset", response_model=schemas.CharacterOut)
def reset_character(db: Session = Depends(get_db)):
    """캐릭터를 처음부터 다시 만든다. 대화가 길어져 꼬였을 때 빠져나갈 길이 필요하다.

    그려둔 그림 파일(media/)은 지우지 않는다 — 참조만 끊는다. 되살릴 일이 있을 수 있고,
    지우는 건 언제든 나중에 할 수 있지만 되돌리는 건 못 한다.
    """
    char = _get(db)
    for field in sheet.ORDER:
        setattr(char, field, "")
    char.keywords = []
    char.editing = ""
    char.pending = {}
    char.confirmed = False
    char.candidates = []
    char.selected_index = -1
    char.messages = []
    return _out(char, db)


def _archive_mascot(char, db: Session) -> None:
    """확정한 마스코트를 보관소에 한 장 남긴다.

    `character` 는 행 하나라 새로 만들면 이전 것이 덮어써진다. 여기서 사본을
    떠 두지 않으면 공들여 만든 마스코트를 되찾을 길이 없다.

    같은 내용을 두 번 쌓지 않는다 — 확정을 다시 눌러도(시트를 고치고 재확정)
    시트와 고른 그림이 그대로면 새 장을 안 만든다.
    """
    cands = list(char.candidates or [])
    i = char.selected_index if char.selected_index is not None else -1
    image = (cands[i] or {}).get("image", "") if 0 <= i < len(cands) else ""
    # 🔴 퍼스널 키워드도 같이 담는다. ORDER 에는 없지만 _require_full_sheet 는 그 칸도
    # 본다 — 안 담으면 불러온 뒤 "퍼스널 키워드가 남았다"며 재확정이 막힌다(실측).
    snapshot = {f: sheet.value_of(char, f) for f in sheet.ORDER}
    snapshot[sheet.KEYWORDS_FIELD] = list(char.keywords or [])

    last = db.query(models.Mascot).order_by(models.Mascot.id.desc()).first()
    if last and last.sheet == snapshot and last.image == image:
        return

    db.add(models.Mascot(
        name=char.name or "",
        sheet=snapshot,
        image=image,
        candidates=cands,
        selected_index=i,
        created_at=_kst_now_text(),
    ))


def _kst_now_text() -> str:
    """보관 시각. 서버는 UTC라 그냥 now()를 쓰면 한국 시간 오전 9시 전에 날짜가
    하루 밀린다(storyboard._kst_now 와 같은 이유)."""
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")


@router.post("/confirm", response_model=schemas.CharacterOut)
def confirm_character(db: Session = Depends(get_db)):
    char = _get(db)
    _require_full_sheet(char)
    if char.selected_index < 0:
        raise HTTPException(400, "마음에 드는 그림을 먼저 골라주세요")
    char.confirmed = True
    _archive_mascot(char, db)
    return _out(char, db)


@router.get("/mascots", response_model=list[schemas.MascotOut])
def list_mascots(db: Session = Depends(get_db)):
    """보관소의 마스코트 목록. 최근 것부터."""
    return db.query(models.Mascot).order_by(models.Mascot.id.desc()).all()


@router.post("/mascots/{mascot_id}/use", response_model=schemas.CharacterOut)
def use_mascot(mascot_id: int, db: Session = Depends(get_db)):
    """보관소의 마스코트를 **지금 쓰는 캐릭터로 불러온다.** 불러온 뒤 대화로 고칠 수 있다.

    보관소의 원본은 그대로 둔다 — 불러와서 고쳐도 지난 마스코트가 바뀌지 않는다.
    고친 것을 다시 확정하면 그때 새 장으로 쌓인다(_archive_mascot).

    확정 상태로 불러온다. 이미 그림까지 고른 마스코트라 다시 고르라고 할 이유가 없다.
    """
    m = db.get(models.Mascot, mascot_id)
    if not m:
        raise HTTPException(404, "그 마스코트가 없어요")

    char = _get(db)
    for field in sheet.ORDER:
        setattr(char, field, (m.sheet or {}).get(field, "") or "")
    kw = (m.sheet or {}).get(sheet.KEYWORDS_FIELD) or []
    # 옛 장은 키워드를 안 담았거나 쉼표 문자열로 담았을 수 있다.
    char.keywords = kw if isinstance(kw, list) else [k.strip() for k in str(kw).split(",") if k.strip()]
    char.candidates = list(m.candidates or [])
    char.selected_index = m.selected_index if m.selected_index is not None else -1
    char.confirmed = True
    char.editing = ""
    char.pending = {}
    messages = list(char.messages or [])
    _say(messages, f"보관소에서 '{m.name or '마스코트'}'를 불러왔어요. "
                   "고치고 싶은 곳이 있으면 말씀해주세요.")
    char.messages = messages
    return _out(char, db)


@router.delete("/mascots/{mascot_id}")
def delete_mascot(mascot_id: int, db: Session = Depends(get_db)):
    """보관소에서 한 장 지운다. 그림 파일은 안 지운다 — 다른 광고가 쓰고 있을 수 있다."""
    m = db.get(models.Mascot, mascot_id)
    if not m:
        raise HTTPException(404, "그 마스코트가 없어요")
    db.delete(m)
    db.commit()
    return {"ok": True}
