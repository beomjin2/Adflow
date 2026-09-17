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
from app.services.chat_ai import character_prompt, new_pid, pending_candidates
from app.services.image_gen import eta_seconds, generate_images

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/character", tags=["character"])


def _get(db: Session) -> models.Character:
    char = db.get(models.Character, 1)
    if not char:
        raise HTTPException(404, "character row missing")
    return char


def _out(char, db: Session) -> schemas.CharacterOut:
    db.commit()
    db.refresh(char)
    return schemas.character_out(char, queue_depth=jobs.queue_depth())


def _say(messages: list, text: str) -> None:
    messages.append({"role": "ai", "kind": "text", "text": text})


def _fill_slots(field: str, indexes: list[int], prompt: str, count: int) -> None:
    """백그라운드 작업 본체 — 이미지를 뽑아 candidates의 해당 칸에 채운다.

    실패하면 status를 'failed'로 남긴다. 조용히 사라지면 사장님은 계속 기다리게 된다.
    """
    images = generate_images(prompt, count)

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
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "내용을 입력해주세요")

    messages = list(char.messages or [])
    messages.append({"role": "me", "kind": "text", "text": text})

    complete_before = sheet.is_complete(char)
    # 우리가 **실제로 물어본** 칸. 비어 있으면 아직 아무것도 묻지 않았다는 뜻이다.
    asked = char.editing

    # LLM이 붙어 있으면 한 문장에서 여러 칸을 한 번에 읽는다
    # ("앞치마 두른 3살 곰이요" → 외형·아웃핏·나이). 못 읽으면 빈 dict가 온다.
    read = sheet_llm.read_fields(char, text, asked or sheet.next_field(char))

    if not complete_before:
        # ---- 빈 칸 채우기 ----
        # 시트에 넣는 건 **LLM이 문장에서 실제로 읽어낸 것**뿐이다.
        #
        # 예전에는 못 읽으면 물어본 칸에 사장님 말을 통째로 넣었다(`{asked: text}`).
        # 그래서 "몰라 좀 해봐"가 설명 칸에, "모른다고"가 능력 칸에 그대로 적혔다.
        # 답이 아닌 말은 답이 아니다. 시트는 사장님이 **정한 것**만 담아야 한다.
        filling = dict(read)
        if not filling and asked and not sheet_llm.available():
            # LLM이 없을 때만 규칙 기반으로 되돌아간다 — 그때는 이것 말고 방법이 없다.
            filling = {asked: text}

        if filling:
            for field, value in filling.items():
                sheet.absorb(char, field, value)
            labels = ", ".join(f"'{sheet.LABELS[f]}'" for f in filling if f in sheet.LABELS)

            following = sheet.next_field(char)
            if following:
                char.editing = following
                _say(messages, _guide(char, text, filling, following,
                                      fallback=f"{labels} 적어뒀어요. {sheet.QUESTIONS[following]}"))
            else:
                # 묻는 칸이 다 찼다 — 키워드를 뽑아 제안한다.
                char.editing = ""
                _say(messages, f"{labels}까지 적어뒀어요. 시트가 다 채워졌어요.")
                _propose_keywords(char, messages)
        else:
            _handle_non_answer(char, messages, text, asked)
    else:
        # ---- 다 찬 뒤의 수정 — 승인받고 반영한다 ----
        # 고칠 칸을 고르지 않았어도 LLM이 어느 칸 얘기인지 읽어낼 수 있다.
        # 여기서도 같다 — 시트에서 칸을 눌러 '이 칸을 고치겠다'고 한 게 asked다.
        # 그게 없으면 무엇을 고치라는 말인지 알 수 없으니 되묻는다.
        changes = read or ({asked: text} if asked else {})
        if not changes:
            _say(
                messages,
                "시트는 다 채워져 있어요. 고치고 싶은 칸을 시트에서 눌러주시면 거기부터 바꿀게요.",
            )
        else:
            _open_suggestion(char, messages, changes)

    char.messages = messages
    return _out(char, db)


def _handle_non_answer(char, messages: list, text: str, asked: str) -> None:
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

    if not asked:
        char.editing = following
        _say(messages, _guide(
            char, text, {}, following,
            fallback=(
                f"캐릭터를 같이 만들어볼게요. {sheet.QUESTIONS[following]}\n"
                "순서대로 안 하셔도 돼요 — 떠오르는 대로 말씀하시면 해당하는 칸에 적어둘게요."
            ),
        ))
        return

    proposal = sheet_llm.propose_field(char, following, text)
    if proposal:
        char.editing = following
        _open_suggestion(char, messages, {following: proposal}, phase="filling")
        return

    # 시트에 넣을 건 없지만 **할 말은 있다.** 질문이었을 수도 있고 고민이었을 수도 있다.
    # 여기서 정해진 문장만 돌려주면 "무슨 말을 해도 같은 소리를 한다"가 된다.
    label = sheet.LABELS[following]
    char.editing = following
    _say(messages, _guide(
        char, text, {}, following,
        fallback=(
            f"방금 말씀은 시트에 넣지 않았어요. '{label}'은(는) 편하게 적어주셔도 되고, "
            "정하기 어려우시면 '알아서 정해줘'라고 하시면 제가 하나 제안해 드릴게요."
        ),
    ))


def _guide(char, text: str, filled: dict, ask_field: str, fallback: str) -> str:
    """사장님 말에 대답하고 다음 칸을 묻는 한 문단. LLM이 못 하면 정해진 문장으로.

    정해진 문장(`fallback`)은 누구에게나 똑같다. 그래서 "캐릭터화하면 뭘 하면
    좋을까"라는 질문에도 "무엇을 입고 있으면 좋을까요?"로 답했다. 대화를 하려면
    **방금 한 말을 읽고 답해야** 한다. 실패하면 조용히 정해진 문장으로 돌아간다 —
    대화가 멈추는 것보다 딱딱한 게 낫다.
    """
    return sheet_llm.reply(char, text, filled, ask_field) or fallback


def _propose_keywords(char, messages: list) -> None:
    """퍼스널 키워드를 자동으로 뽑아 승인 카드로 올린다.

    뽑을 말이 없으면 지어내지 않고 사장님에게 직접 묻는다. 그럴듯한 형용사를 채워
    넣으면 그건 사장님이 정한 적 없는 성격이 된다.
    """
    # LLM이 붙어 있으면 문장의 뜻을 보고 고른다. 없으면 사장님이 쓴 형용사를 집어낸다.
    guessed = sheet_llm.suggest_keywords(char) or sheet.derive_keywords(char)
    if not guessed:
        char.editing = sheet.KEYWORDS_FIELD
        _say(
            messages,
            "마지막으로 퍼스널 키워드만 남았어요. 적어주신 글에서 뽑아낼 말을 못 찾았어요 — "
            "이 캐릭터를 한마디로 말하면 어떤 느낌인가요? 쉼표로 여러 개 적으셔도 돼요.",
        )
        return

    proposed = ", ".join(guessed)
    pending = dict(char.pending or {})
    pid = new_pid()
    pending[pid] = {
        "kind": "keywords",
        "field": sheet.KEYWORDS_FIELD,
        "diffs": sheet.diff_for(char, sheet.KEYWORDS_FIELD, proposed),
        "payload": {"keywords": guessed},
        "status": "open",
    }
    char.pending = pending
    _say(
        messages,
        f"적어주신 내용에서 퍼스널 키워드를 이렇게 정했어요 — {proposed}. "
        "이대로 둘까요? 마음에 안 드시면 직접 적어주셔도 돼요.",
    )
    messages.append({"role": "ai", "kind": "confirm", "pid": pid})


def _open_suggestion(char, messages: list, changes: dict, phase: str = "editing") -> None:
    """수정 제안을 승인 대기로 올린다. 한 문장이 여러 칸을 건드리면 한 카드에 모아 보여준다.

    phase는 승인 뒤 어디로 이어갈지를 정한다.
      - "editing"  — 다 찬 시트를 고치는 중. 가이드 순서상 다음 칸을 이어서 물어본다.
      - "filling"  — 아직 빈 칸을 채우는 중. 가이드가 아니라 **남은 빈 칸**으로 이어간다.
    """
    # 지금과 같은 값은 뺀다 — "바꿀까요?"라고 물으면서 같은 걸 보여주면 안 된다.
    real = {f: v for f, v in changes.items() if f in sheet.ORDER and sheet.value_of(char, f) != v}
    if not real:
        _say(messages, "지금 시트와 같은 내용이에요. 그대로 둘게요.")
        return

    diffs = []
    for field, value in real.items():
        diffs.extend(sheet.diff_for(char, field, value))

    pending = dict(char.pending or {})
    pid = new_pid()
    pending[pid] = {
        "kind": "field",
        "phase": phase,
        # 승인 뒤 가이드 제안의 기준점. 여러 칸이면 가이드 순서상 가장 뒤쪽을 기준으로 삼는다.
        "field": max(real, key=sheet.ORDER.index),
        "diffs": diffs,
        "payload": {"changes": real},
        "status": "open",
    }
    char.pending = pending
    labels = ", ".join(f"'{sheet.LABELS[f]}'" for f in real)
    if phase == "filling":
        _say(messages, f"그럼 {labels}은(는) 이렇게 하면 어떨까요?")
    else:
        _say(messages, f"{labels}을(를) 이렇게 바꿀까요?")
    messages.append({"role": "ai", "kind": "confirm", "pid": pid})


@router.post("/suggestions/{pid}/accept", response_model=schemas.CharacterOut)
def accept_suggestion(pid: str, db: Session = Depends(get_db)):
    """제안을 반영하고, 가이드 순서상 다음 칸도 고칠지 물어본다."""
    char = _get(db)
    pending = dict(char.pending or {})
    proposal = pending.get(pid)
    if not proposal:
        raise HTTPException(404, "그 제안을 찾을 수 없어요")
    if proposal.get("status") != "open":
        raise HTTPException(400, "이미 처리된 제안이에요")

    pending[pid] = {**proposal, "status": "applied"}
    char.pending = pending
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
        label = ", ".join(sheet.LABELS[f] for f in changes)

        if proposal.get("phase") == "filling":
            # 빈 칸을 대신 정해준 제안이었다. 가이드가 아니라 **남은 빈 칸**으로 이어간다.
            following = sheet.next_field(char)
            if following:
                char.editing = following
                _say(messages, f"{label} 그렇게 적어뒀어요. {sheet.QUESTIONS[following]}")
            else:
                char.editing = ""
                _say(messages, f"{label}까지 적어뒀어요. 시트가 다 채워졌어요.")
                _propose_keywords(char, messages)
        else:
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
            f"그럼 '{sheet.LABELS[field]}'은(는) 사장님이 정해주세요. {sheet.QUESTIONS.get(field, '')}",
        )
    else:
        _say(messages, "그대로 둘게요. 어떻게 바꾸면 좋을지 다시 적어주세요.")

    char.messages = messages
    return _out(char, db)


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


@router.post("/candidates", response_model=schemas.CharacterOut)
def gen_candidates(db: Session = Depends(get_db)):
    """후보 3장을 뽑는다. **사장님이 버튼을 눌렀을 때만** 여기 온다."""
    char = _get(db)
    _require_full_sheet(char)

    char.candidates = pending_candidates(3)
    char.selected_index = -1
    messages = list(char.messages or [])
    _say(messages, f"시트대로 3장 그려볼게요. 약 {eta_seconds(3)}초 걸려요 — 창을 닫으셔도 서버에서 계속 그립니다.")
    messages.append({"role": "ai", "kind": "cands", "ref": "cands"})
    char.messages = messages
    db.commit()

    jobs.submit(_fill_slots, "candidates", [0, 1, 2], character_prompt(char), 3)

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

    jobs.submit(
        _fill_slots, "candidates", [index],
        character_prompt(char, f"variation {index + 1}"), 1,
    )

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


@router.post("/confirm", response_model=schemas.CharacterOut)
def confirm_character(db: Session = Depends(get_db)):
    char = _get(db)
    _require_full_sheet(char)
    if char.selected_index < 0:
        raise HTTPException(400, "마음에 드는 그림을 먼저 골라주세요")
    char.confirmed = True
    return _out(char, db)
