"""광고 구성(스토리보드) 대화.

두 가지가 빠져 있다. 의도한 것이다.
- **트렌드 조사**: 제거됐다. 어디서 가져왔는지 댈 수 없는 순위·조회수를 근거로
  사장님에게 광고를 권할 수는 없다.
- **광고 이미지 생성**: 컷 구성이 정해진 뒤 `POST /comic`으로만 만든다(MVP). 확정한
  캐릭터 그림을 참조로 넣어 컷마다 한 장씩 백그라운드에서 그린다. 대사·글자는 그림에
  넣지 않는다 — 그림 모델은 글자를 못 쓴다.

컷 구성은 **사장님이 쓴 말을 GPT가 컷으로 나눈 것**이다(`story_llm.plan_from_text`).
템플릿은 없다. 키가 없거나 호출이 실패하면 예전 경로 — 문장부호에서 자르는
`_cuts_from_text` — 로 조용히 되돌아간다. 어느 쪽이든 만든 구성을 바로 반영하지 않고
confirm 카드로 올려 사장님이 승인해야 plan이 된다. 서비스가 문장을 만드는 자리라 그렇다.

스토리 제안은 자동으로 뜨지 않는다 — 사장님이 직접 적거나(POST /chat), 대화창의
"스토리 제안받기" 버튼을 눌러야(POST /suggest) 만든다. 밈은 트렌드 화면에서 미리
골라 왔을 때만(`Storyboard.trend_meme_id`) 반영한다 — 안 골랐으면 밈 얘기 자체를
꺼내지 않는다. GPT가 크롤링된 밈 중 스스로 골라 끼워 넣게 하면 사장님이 고른 적
없는 밈이 광고에 섞일 수 있어서다. 카드를 만들거나 고르는 별도 화면도 없다.

대화 중에 밈을 새로 추천받고 싶으면 "밈 추천받기" 버튼을 눌러야(POST /recommend-meme)
한다 — 이때는 지금까지 사장님이 대화에서 쓴 문장을 근거로 trend/recommend.py와 같은
GPT 추천(meme_recommend.recommend)을 한 번 더 돌린다. 결과도 confirm 카드로 올려
승인해야 trend_meme_id가 바뀐다(kind="meme").

생산 기록은 여기서 안 받는다 — "내 정보 > 생산 기록" 탭에서만 남긴다. 예전엔 대화
첫 마디를 생산 기록으로 파싱했는데, 대화 한 번으로 두 가지 일을 하는 게 헷갈린다는
판단으로 뺐다. `_plan_cuts`가 매번 최근 생산 기록을 조회해서 스토리에 반영하는 건
그대로다 — 그 기록을 만드는 자리만 옮긴 것이다.
"""

import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.config import settings
from app.core.database import get_db
from app.services import comic_bake, director, jobs, sign_check, story_llm, trace
from app.services.chat_ai import (COMIC_GLOBAL_TAGS, COMIC_IDENTITY_FIELDS, character_part, comic_prompt,
                                  comic_prompt_slots, new_pid)
from app.services.danbooru_lookup import verify_tags
from app.services.image_gen import _save_png, generate_images
from app.services.meme_recommend import recommend as recommend_meme

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/storyboard", tags=["storyboard"])

MAX_CUTS = 4

# 문장 끝 또는 줄바꿈에서 자른다. 사장님이 "손님이 들어온다. 빵을 본다." 처럼 쓰면
# 그대로 두 컷이 된다.
_SPLIT_RE = re.compile(r"[\n.!?·]+|,\s*(?=그리고|그다음|그 다음|마지막)")


def _get(db: Session) -> models.Storyboard:
    sb = db.get(models.Storyboard, 1)
    if not sb:
        raise HTTPException(404, "storyboard row missing")
    return sb


def _require_character(db: Session) -> models.Character:
    """스토리를 만드는 자리(POST /chat의 스토리 단계, POST /suggest)는 전부 여기부터 거친다.

    광고 설정을 확정할 때(POST /api/ad/apply)도 캐릭터 확정을 이미 확인하지만, 그건
    스토리보드에 들어오는 시점의 검사다 — 들어온 뒤에 캐릭터를 다시 고치거나 초기화하면
    이 화면은 그대로 열려 있을 수 있다. 스토리는 마스코트 정보(이름·외형 등)를 그대로
    쓰므로, 만드는 순간에도 한 번 더 확인한다.
    """
    char = db.get(models.Character, 1)
    if not char or not char.confirmed:
        raise HTTPException(400, "캐릭터를 먼저 확정해주세요 — 스토리에 마스코트 정보가 들어가요")
    return char


def reset_storyboard(db: Session, trend_meme_id: str | None = None) -> models.Storyboard:
    """광고 설정을 확정했을 때 스토리보드를 처음 상태로 되돌린다.

    trend_meme_id — 트렌드 화면에서 미리 골라 온 밈(있으면). 이번 광고 내내 대화가
    참고한다(_meme_context 참고).

    스토리 제안은 자동으로 뜨지 않는다 — 사장님이 대화창에 직접 적거나, "스토리
    제안받기" 버튼을 눌러야(POST /api/storyboard/suggest) 만든다.
    """
    sb = _get(db)
    sb.messages = []
    sb.plan = []
    sb.comic_cuts = []
    sb.pending = {}
    sb.trend_meme_id = trend_meme_id or ""
    meme = db.get(models.Meme, trend_meme_id) if trend_meme_id else None
    sb.trend_meme_name = meme.meme_name if meme else ""
    db.commit()
    db.refresh(sb)
    return sb


def _cuts_from_text(text: str) -> list[dict]:
    """사장님이 쓴 문장을 컷으로 쪼갠다. 한 문장이면 한 컷이다."""
    parts = [p.strip() for p in _SPLIT_RE.split(text or "")]
    parts = [p for p in parts if p][:MAX_CUTS]
    return [
        {"n": i + 1, "short": p[:14], "line": p}
        for i, p in enumerate(parts)
    ]


def _chat_note(messages: list[dict]) -> str:
    """대화창에서 사장님이 직접 쓴 문장만 모아 이어 붙인다. "스토리 제안받기"·"밈
    추천받기" 둘 다 버튼을 눌렀을 때 지금까지 나눈 얘기를 재료로 쓰려고 같이 쓴다."""
    return " ".join(
        (m.get("text") or "") for m in messages if m.get("role") == "me" and m.get("kind") == "text"
    ).strip()


def _meme_context(sb: models.Storyboard, db: Session) -> dict | None:
    """트렌드 화면에서 미리 골라 온 밈이 있을 때만 그걸 돌려준다. 안 골랐으면 None —
    GPT가 스스로 후보를 뒤져 끼워 넣게 하면 사장님이 고른 적 없는 밈이 광고에 섞일 수 있다."""
    if sb.trend_meme_id:
        m = db.get(models.Meme, sb.trend_meme_id)
        if m:
            return {"id": m.id, "name": m.meme_name, "origin": m.origin,
                    "usage_example": m.usage_example}
    return None


def _plan_cuts(text: str, sb: models.Storyboard, db: Session) -> tuple[list[dict], dict | None] | None:
    """사장님 문장 → (컷 구성, 반영한 밈).

    GPT가 있으면 GPT가 가게·캐릭터·광고 느낌·(있으면) 밈을 함께 보고 컷으로 나눈다. 못 쓰면
    (키 없음·호출 실패·형식 이상) 문장부호에서 자르는 옛 규칙으로 조용히 되돌아간다(이땐
    밈은 반영 안 됨).

    **None은 "규칙으로도 되돌아가지 않는다"는 뜻이다.** GPT가 사장님 말을 인사·잡담으로
    본 경우에만 나온다 — 그때 규칙으로 쪼개면 "안녕하세요"가 1컷이 되어 버린다.
    """
    store = db.get(models.Store, 1)
    char = db.get(models.Character, 1)
    ad = db.get(models.AdSettings, 1)
    prods = (
        db.query(models.ProductionRecord)
        .order_by(models.ProductionRecord.id.desc()).limit(10).all()
    )
    trend_meme = _meme_context(sb, db)
    store_d = {"category": store.category, "address": store.address, "hours": store.hours, "desc": store.desc} if store else {}
    char_d = {"name": char.name, "look": char.look, "outfit": char.outfit, "desc": char.desc} if char else {}
    ad_d = {"ad_type": ad.ad_type, "ad_concept": ad.ad_concept} if ad else {}
    prods_d = [{"name": p.name, "qty": p.qty, "date": p.date, "time": p.time, "sold_out": p.sold_out} for p in prods]
    # 뜯어보기: 광고 하나의 단계별 기록을 여기서 시작한다. 컷에 trace_id 를 실어 그림 단계가 이어 쓴다.
    tr = trace.Tracer.start(kind="comic", text=text[:80])
    tr.step("입력 모으기", who="code", said=text, store=store_d, character=char_d, ad=ad_d, production=prods_d,
            trend_meme=trend_meme, current_plan=list(sb.plan or []))
    with trace.use(tr):
        proposed = story_llm.plan_from_text(
            text, store=store_d, char=char_d, ad=ad_d, prods=prods_d,
            current_plan=list(sb.plan or []), trend_meme=trend_meme,
        )
    if proposed is None:
        tr.step("대사 정리", who="code", note="GPT 를 못 써 문장부호로 잘랐다", cuts=_cuts_from_text(text))
        return [{**c, "trace_id": tr.run_id} for c in _cuts_from_text(text)], None
    if not proposed["cuts"]:
        tr.step("대사 정리", who="code", note="GPT 가 광고 내용이 아니라고 봄")
        return None
    tr.step("대사 정리", who="code", cuts=proposed["cuts"], meme_used=proposed["meme_used"],
            view=f"/api/debug/trace/{tr.run_id}/view")
    return [{**c, "trace_id": tr.run_id} for c in proposed["cuts"]], proposed["meme_used"]


def _propose_intro(meme_used: dict | None) -> str:
    if meme_used:
        return (
            f"'{meme_used['name']}' 밈도 참고해서 스토리를 만들었어요. "
            "마음에 들면 아래에서 이대로 바꾸기를 눌러주세요."
        )
    return "스토리를 만들었어요. 마음에 들면 아래에서 이대로 바꾸기를 눌러주세요."


def _propose_plan(sb: models.Storyboard, cuts: list[dict], messages: list[dict]) -> None:
    """만든 컷 구성을 확인 카드로 올린다. 승인하기 전까지 plan은 바뀌지 않는다."""
    current = list(sb.plan or [])
    diffs = []
    for cut in cuts:
        before = next((c["line"] for c in current if c.get("n") == cut["n"]), "아직 없음")
        action = cut.get("action") or ""
        diffs.append({
            "label": f"{cut['n']}컷",
            "from": before,
            "to": f"{cut['line']} — {action}" if action else cut["line"],
        })
    for old in current[len(cuts):]:
        diffs.append({"label": f"{old['n']}컷", "from": old["line"], "to": "삭제"})

    pending = dict(sb.pending or {})
    pid = new_pid()
    pending[pid] = {
        "which": "sb", "kind": "plan", "diffs": diffs,
        "payload": {"plan": cuts}, "status": "open",
    }
    sb.pending = pending
    messages.append({"role": "ai", "kind": "confirm", "pid": pid})


@router.get("", response_model=schemas.StoryboardOut)
def get_storyboard(db: Session = Depends(get_db)):
    return schemas.storyboard_out(_get(db), jobs.queue_depth())


@router.post("/chat", response_model=schemas.StoryboardOut)
def chat(body: schemas.ChatIn, db: Session = Depends(get_db)):
    """스토리보드 채팅 — 사장님이 쓴 내용으로 컷 구성을 만든다.

    생산 기록은 여기서 안 받는다("내 정보 > 생산 기록" 탭에서만 남긴다) — 대화는
    스토리를 만드는 자리다. 만든 구성은 바로 반영하지 않고 confirm 카드로 보여준다 —
    사장님이 '이렇게 바뀝니다'를 보고 승인해야 실제로 반영된다.
    """
    sb = _get(db)
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "내용을 입력해주세요")

    messages = list(sb.messages or [])
    messages.append({"role": "me", "kind": "text", "text": text})

    _require_character(db)
    result = _plan_cuts(text, sb, db)
    if result is None:
        # GPT가 "광고로 만들 내용이 아니다"라고 본 경우다. 여기서 아무 장면이나
        # 만들면 사장님이 말한 적 없는 광고가 된다 — 지어내지 말고 되묻는다.
        messages.append({
            "role": "ai", "kind": "text",
            "text": "그 말씀만으로는 광고 장면을 잡기 어려워요. 오늘 알리고 싶은 걸 한 줄로 적어주세요.",
        })
    else:
        cuts, meme_used = result
        if not cuts:
            messages.append({
                "role": "ai", "kind": "text",
                "text": "어떤 장면인지 한 문장으로 적어주세요. 문장 하나가 한 컷이 돼요.",
            })
        else:
            messages.append({"role": "ai", "kind": "text", "text": _propose_intro(meme_used)})
            _propose_plan(sb, cuts, messages)

    sb.messages = messages
    db.commit()
    db.refresh(sb)
    return schemas.storyboard_out(sb, jobs.queue_depth())


@router.post("/suggest", response_model=schemas.StoryboardOut)
def suggest(db: Session = Depends(get_db)):
    """대화창의 "스토리 제안받기" 버튼 — 자동으로는 절대 안 뜬다(사장님이 버튼을
    눌러야만 부른다). 지금까지 대화에서 사장님이 쓴 문장이 있으면 그걸 재료로 쓰고,
    없으면(정말 아무것도 안 쓰고 눌렀으면) 가게·캐릭터·최근 생산 기록·(있으면)
    밈만으로 스토리를 만든다.
    """
    sb = _get(db)
    _require_character(db)
    messages = list(sb.messages or [])
    note = _chat_note(messages)
    text = note or "(사장님이 따로 말하지 않음 — 가게·캐릭터·최근 생산 기록을 재료로 이야기를 만든다)"
    result = _plan_cuts(text, sb, db)
    if result is None or not result[0]:
        messages.append({
            "role": "ai", "kind": "text",
            "text": "지금 있는 정보만으로는 스토리를 만들기 어려워요. 오늘 알리고 싶은 걸 한 줄로 적어주세요.",
        })
    else:
        cuts, meme_used = result
        messages.append({"role": "ai", "kind": "text", "text": _propose_intro(meme_used)})
        _propose_plan(sb, cuts, messages)
    sb.messages = messages
    db.commit()
    db.refresh(sb)
    return schemas.storyboard_out(sb, jobs.queue_depth())


@router.post("/recommend-meme", response_model=schemas.StoryboardOut)
async def recommend_meme_from_chat(db: Session = Depends(get_db)):
    """대화창의 "밈 추천받기" 버튼 — 자동으로는 안 뜬다. 지금까지 사장님이 대화에서 쓴
    문장을 모아 trend/recommend.py와 같은 GPT 추천(meme_recommend.recommend)을 돌리고,
    결과를 confirm 카드로 올린다. 승인해야만 trend_meme_id가 바뀐다 — 대화 흐름만 보고
    GPT가 알아서 밈을 끼워 넣지 않는다.
    """
    sb = _get(db)
    messages = list(sb.messages or [])
    note = _chat_note(messages)
    if not note:
        messages.append({
            "role": "ai", "kind": "text",
            "text": "대화에서 알릴 내용을 먼저 말씀해주시면 그걸 보고 밈을 추천해드릴게요.",
        })
        sb.messages = messages
        db.commit()
        db.refresh(sb)
        return schemas.storyboard_out(sb, jobs.queue_depth())

    all_memes = [m for m in db.query(models.Meme).all() if m.situation and m.situation != "미분류"]
    if not all_memes:
        messages.append({"role": "ai", "kind": "text", "text": "지금 추천할 수 있는 밈이 없어요."})
        sb.messages = messages
        db.commit()
        db.refresh(sb)
        return schemas.storyboard_out(sb, jobs.queue_depth())

    store = db.get(models.Store, 1)
    store_desc = ""
    if store and store.saved:
        parts = [store.category, store.address, store.hours, store.desc]
        store_desc = " / ".join(p for p in parts if p)

    char = db.get(models.Character, 1)
    character_desc = ""
    if char and char.confirmed:
        parts = [char.name, char.look, char.outfit, char.abilities, ", ".join(char.keywords or []), char.desc]
        character_desc = " / ".join(p for p in parts if p)

    try:
        result = await recommend_meme(
            note, character_desc, store_desc,
            candidates=[
                {"id": m.id, "name": m.meme_name, "situation": m.situation,
                 "origin": m.origin, "usage_example": m.usage_example}
                for m in all_memes
            ],
        )
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception:
        logger.exception("대화 기반 밈 추천 실패")
        raise HTTPException(502, "추천을 만들지 못했어요. 잠시 뒤 다시 시도해 주세요")

    by_id = {m.id: m for m in all_memes}
    pick = result["picks"][0]
    meme = by_id[pick["meme_id"]]

    pending = dict(sb.pending or {})
    pid = new_pid()
    pending[pid] = {
        "which": "sb", "kind": "meme",
        "diffs": [{"label": "트렌드 밈", "from": sb.trend_meme_name or "아직 없음", "to": meme.meme_name}],
        "why": pick["reason"],
        "payload": {"meme_id": meme.id, "meme_name": meme.meme_name},
        "status": "open",
    }
    sb.pending = pending
    messages.append({
        "role": "ai", "kind": "text",
        "text": f"지금까지 나눈 얘기를 보니 '{meme.meme_name}' 밈이 어울릴 것 같아요.",
    })
    messages.append({"role": "ai", "kind": "confirm", "pid": pid})
    sb.messages = messages
    db.commit()
    db.refresh(sb)
    return schemas.storyboard_out(sb, jobs.queue_depth())


def _reference_path(char) -> Path | None:
    """확정한 후보 그림의 디스크 경로. /api/media/<파일명> URL을 media_path의 파일로 되돌린다."""
    cands = list(char.candidates or [])
    index = char.selected_index if char.selected_index is not None else -1
    if not 0 <= index < len(cands):
        return None
    image = (cands[index] or {}).get("image") or ""
    name = image.rsplit("/", 1)[-1]
    path = settings.media_path / name if name else None
    return path if path and path.is_file() else None


# 마지막 컷 규칙 — 가게 앞 전경(wide_shot) + 캐릭터 오른쪽(크롭) + 왼쪽 아래 코드 입간판.
# sign 태그는 일부러 뺀다: 넣으면 모델이 제 칠판을 그려 우리 입간판과 두 개가 된다(09-22 실측).
_STOREFRONT_TAGS = ["wide_shot", "full_body", "solo", "outdoors", "shop", "door", "standing", "waving", "smile", "looking_at_viewer"]
_SIGN_RETRIES = 2


def _storefront_prompt(char_part_text: str) -> str:
    return ", ".join(p for p in [COMIC_GLOBAL_TAGS, char_part_text, ", ".join(verify_tags(_STOREFRONT_TAGS))] if p)


def _fill_cuts(indexes: list[int], scenes: list[dict], char_part_text: str, reference: Path,
               trace_id: str | None = None, board_lines: list[str] | None = None) -> None:
    """백그라운드 본체 — 컷마다 프롬프트를 만들고 한 장씩 뽑아 comic_cuts의 칸을 채운다.
    scenes[i] = {"text", "camera", "slots"(연출, 없을 수 있음), "last": 마지막 컷인가, "n", "line"}.
    슬롯이 있으면 연출 경로(comic_prompt_slots + 위치 크롭), 없으면 옛 경로(comic_prompt).
    마지막 컷은 가게 앞 전경 + 간판 검사·재시도 + 입간판 굽기. 다 끝나면 2×2 완성본을 만든다.
    trace_id 가 있으면 제안 때 시작한 단계별 기록에 이어 쓴다(다른 스레드라 여기서 다시 잡는다)."""
    tr = trace.Tracer.resume(trace_id)
    with trace.use(tr):
        for index, scene in zip(indexes, scenes):
            slots = scene.get("slots")
            slot_trace = None
            position = None
            tries: list[dict] = []
            if scene.get("last"):
                prompt = _storefront_prompt(char_part_text)
                position = "오른쪽"
                trace.step(f"컷 {scene.get('n')} 규칙", who="code", rule="마지막 컷 = 가게 앞 전경 + 캐릭터 오른쪽 + 왼쪽 아래 입간판", prompt=prompt)
                image = None
                for attempt in range(_SIGN_RETRIES + 1):
                    images = generate_images(prompt, 1, workflow_file=settings.comfy_comic_workflow_file,
                                             reference_path=reference, position=position)
                    image = images[0] if images else None
                    if not image:
                        break
                    hit = sign_check.sign_tags(settings.media_path / image.rsplit("/", 1)[-1])
                    tries.append({"attempt": attempt + 1, "image": image, "sign_tags": hit})
                    trace.step(f"컷 {scene.get('n')} 간판 검사 {attempt + 1}회", who="wd14", image=image, sign_tags=hit,
                               verdict="검사 없음(태거 없음)" if hit is None else ("다시" if hit and attempt < _SIGN_RETRIES else "채택"))
                    if not hit:
                        break
                if image and board_lines:
                    from PIL import Image
                    src = settings.media_path / image.rsplit("/", 1)[-1]
                    baked = comic_bake.board(Image.open(src), board_lines)
                    from io import BytesIO
                    buf = BytesIO(); baked.save(buf, format="PNG")
                    image = _save_png(buf.getvalue()) or image
                    trace.step(f"컷 {scene.get('n')} 입간판 굽기", who="code", lines=board_lines, image=image)
            else:
                if slots:
                    prompt, slot_trace = comic_prompt_slots(char_part_text, slots)
                    position = (slots.get("shot") or {}).get("position")
                else:
                    prompt = comic_prompt(char_part_text, scene.get("text", ""), scene.get("camera", ""))
                trace.step(f"컷 {scene.get('n')} 프롬프트 조립", who="code", prompt=prompt, slot_to_tags=slot_trace, position=position)
                images = generate_images(prompt, 1, workflow_file=settings.comfy_comic_workflow_file,
                                         reference_path=reference, position=position)
                image = images[0] if images else None

            def write(db: Session, index=index, image=image, prompt=prompt, slot_trace=slot_trace, tries=tries):
                sb = db.get(models.Storyboard, 1)
                if not sb:
                    return
                cuts = list(sb.comic_cuts or [])
                if 0 <= index < len(cuts):
                    cuts[index] = {**cuts[index], "image": image, "status": "done" if image else "failed",
                                   "prompt": prompt, "trace": slot_trace, "tries": tries}
                    sb.comic_cuts = cuts
                    db.commit()

            jobs.with_session(write)
        _compose_if_done()


def _compose_if_done() -> None:
    """모든 컷이 done 이면 말풍선을 굽고 2×2 로 합쳐 완성본 URL 을 각 컷의 final 에 적는다."""
    from PIL import Image

    def run(db: Session):
        sb = db.get(models.Storyboard, 1)
        if not sb:
            return
        cuts = list(sb.comic_cuts or [])
        if not cuts or any(c.get("status") != "done" or not c.get("image") for c in cuts):
            return
        panels = []
        for c in cuts:
            im = Image.open(settings.media_path / c["image"].rsplit("/", 1)[-1])
            side = comic_bake.bubble_side(((c.get("slots") or {}).get("shot") or {}).get("position"), c.get("n", 1))
            panels.append(comic_bake.bubble(im, c.get("line", ""), side))
        from io import BytesIO
        buf = BytesIO(); comic_bake.compose(panels).save(buf, format="PNG")
        final = _save_png(buf.getvalue())
        sb.comic_cuts = [{**c, "final": final} for c in cuts]
        db.commit()
        trace.step("말풍선 굽기 · 2×2 합치기", who="code", final=final)

    jobs.with_session(run)


def _start_cuts(sb: models.Storyboard, char: models.Character, indexes: list[int], db: Session) -> None:
    reference = _reference_path(char)
    if reference is None:
        raise HTTPException(400, "캐릭터를 먼저 확정해주세요 — 확정한 캐릭터 그림을 참조로 씁니다")
    cuts = list(sb.comic_cuts or [])
    last = len(cuts) - 1
    # 그림엔 대사가 아니라 동작을 넣는다(대사·글자는 말풍선 몫). 동작이 없으면(직접 쓴 컷) 대사 문장을 쓴다.
    scenes = [{"n": cuts[i].get("n", i + 1), "line": cuts[i].get("line", ""),
               "text": cuts[i].get("action") or cuts[i].get("line", ""), "camera": cuts[i].get("camera", ""),
               "slots": cuts[i].get("slots"), "last": i == last}
              for i in indexes]
    for i in indexes:
        cuts[i] = {**cuts[i], "image": None, "status": "generating", "final": None}
    sb.comic_cuts = cuts
    db.commit()
    # 입간판 글 — 가게 정보 + 최근 생산 기록
    store = db.get(models.Store, 1)
    prods = db.query(models.ProductionRecord).order_by(models.ProductionRecord.id.desc()).limit(1).all()
    board_lines = comic_bake.board_lines(
        {"hours": store.hours, "address": store.address} if store else {},
        [{"name": p.name, "qty": p.qty} for p in prods])
    # 뜯어보기: 제안 때 시작한 기록(trace_id)에 이어 쓴다. 캐릭터 태깅도 그 기록 안에.
    trace_id = next((c.get("trace_id") for c in cuts if c.get("trace_id")), None)
    tr = trace.Tracer.resume(trace_id)
    with trace.use(tr):
        trace.step("그림 단계 시작", who="code", cuts=indexes, board_lines=board_lines,
                   character_sheet={"look": char.look, "outfit": char.outfit, "age": char.age})
        # 캐릭터 태그는 여기서 한 번만 계산한다(GPT 1회). 생김새·옷·나이만(COMIC_IDENTITY_FIELDS).
        char_text = character_part(char, COMIC_IDENTITY_FIELDS)
        trace.step("캐릭터 태그 확정", who="code", character_tags=char_text)
    jobs.submit(_fill_cuts, indexes, scenes, char_text, reference, trace_id, board_lines)


@router.post("/comic", response_model=schemas.StoryboardOut)
def make_comic(db: Session = Depends(get_db)):
    """컷 구성 전부를 네컷 그림으로 뽑는다(비동기). 화면은 GET /api/storyboard를 폴링한다."""
    sb = _get(db)
    plan = list(sb.plan or [])
    if not plan:
        raise HTTPException(400, "먼저 대화로 컷 구성을 만들어주세요")
    char = db.get(models.Character, 1)
    if not char or not char.confirmed:
        raise HTTPException(400, "캐릭터를 먼저 확정해주세요")
    # 연출 — 대사·상황을 그림 슬롯으로(크기·각도·위치·시선·표정…). GPT 를 못 쓰면 None → 옛 경로.
    ad = db.get(models.AdSettings, 1)
    trace_id = next((c.get("trace_id") for c in plan if c.get("trace_id")), None)
    with trace.use(trace.Tracer.resume(trace_id)):
        slots = director.direct([c.get("line", "") for c in plan], [c.get("action") or c.get("line", "") for c in plan],
                                (ad.ad_concept if ad else "") or "")
        trace.step("연출 정리", who="code", slots=slots)
    sb.comic_cuts = [
        {"n": c["n"], "short": c.get("short", ""), "line": c.get("line", ""),
         "action": c.get("action", ""), "camera": c.get("camera", ""),
         "slots": slots[i] if slots and i < len(slots) else None, "trace_id": c.get("trace_id"),
         "label": f"{c['n']}컷", "image": None, "status": "generating"}
        for i, c in enumerate(plan)
    ]
    # 네컷은 대화창 안에서 보여준다. 그림이 대화 흐름 밖에서 나오면 사장님은 무엇 때문에
    # 그게 나왔는지 놓친다. 말풍선은 comic_cuts를 그대로 비추므로 **하나만** 둔다 —
    # 다시 그려도 새 말풍선이 생기는 게 아니라 그 자리가 다시 채워진다. 안내 문구도 같이
    # 걷어내야 한다(ref로 표시해 둔다). 말풍선만 지우면 "그릴게요"가 다시 그릴 때마다
    # 한 줄씩 쌓여, 대화 기록만 보면 네 번 그린 것처럼 보인다.
    messages = [
        m for m in list(sb.messages or [])
        if m.get("kind") != "comic" and m.get("ref") != "comic-start"
    ]
    messages.append({
        "role": "ai", "kind": "text", "ref": "comic-start",
        "text": f"정해진 {len(plan)}컷을 그릴게요. 이 화면을 닫아도 서버에서 계속 그립니다.",
    })
    messages.append({"role": "ai", "kind": "comic"})
    sb.messages = messages
    _start_cuts(sb, char, list(range(len(plan))), db)
    db.refresh(sb)
    return schemas.storyboard_out(sb, jobs.queue_depth())


@router.post("/confirm/{pid}", response_model=schemas.StoryboardOut)
def confirm_pending(pid: str, db: Session = Depends(get_db)):
    sb = _get(db)
    pending = dict(sb.pending or {})
    p = pending.get(pid)
    if not p:
        raise HTTPException(404, "pending not found")
    if p.get("status") != "open":
        raise HTTPException(400, "이미 처리된 제안이에요")

    pending[pid] = {**p, "status": "applied"}
    messages = list(sb.messages or [])
    if p["kind"] == "plan":
        sb.plan = p["payload"]["plan"]
        messages.append({"role": "ai", "kind": "plan", "ref": "plan"})
    elif p["kind"] == "meme":
        sb.trend_meme_id = p["payload"]["meme_id"]
        sb.trend_meme_name = p["payload"]["meme_name"]
        messages.append({
            "role": "ai", "kind": "text",
            "text": f"'{p['payload']['meme_name']}' 밈으로 바꿨어요. 다음 스토리부터 이 밈을 참고할게요.",
        })
    sb.pending = pending
    sb.messages = messages
    db.commit()
    db.refresh(sb)
    return schemas.storyboard_out(sb, jobs.queue_depth())


@router.post("/decline/{pid}", response_model=schemas.StoryboardOut)
def decline_pending(pid: str, db: Session = Depends(get_db)):
    sb = _get(db)
    pending = dict(sb.pending or {})
    p = pending.get(pid)
    if not p or p.get("status") != "open":
        raise HTTPException(404, "pending not open")
    pending[pid] = {**p, "status": "declined"}
    messages = list(sb.messages or [])
    messages.append({
        "role": "ai", "kind": "text",
        "text": "그대로 둘게요. 어떻게 바꾸면 좋을지 다시 적어주세요.",
    })
    sb.pending = pending
    sb.messages = messages
    db.commit()
    db.refresh(sb)
    return schemas.storyboard_out(sb, jobs.queue_depth())
