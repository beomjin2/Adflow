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
골라 왔으면(`Storyboard.trend_meme_id`) 그걸 반영하고, 안 골랐으면 GPT가 크롤링된
밈 중 스스로 어울리는 걸 찾아본다 — 카드를 만들거나 고르는 별도 화면은 없다.

생산 기록은 여기서 안 받는다 — "내 정보 > 생산 기록" 탭에서만 남긴다. 예전엔 대화
첫 마디를 생산 기록으로 파싱했는데, 대화 한 번으로 두 가지 일을 하는 게 헷갈린다는
판단으로 뺐다. `_plan_cuts`가 매번 최근 생산 기록을 조회해서 스토리에 반영하는 건
그대로다 — 그 기록을 만드는 자리만 옮긴 것이다.
"""

import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.config import settings
from app.core.database import get_db
from app.services import jobs, story_llm
from app.services.chat_ai import COMIC_IDENTITY_FIELDS, character_part, comic_prompt, new_pid
from app.services.image_gen import generate_images

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


def _meme_context(sb: models.Storyboard, db: Session) -> tuple[dict | None, list[dict]]:
    """(trend_meme, meme_candidates) — 미리 골라 온 밈이 있으면 그것만, 없으면 GPT가
    스스로 볼 후보 목록("미분류"는 진짜 활용 상황이 아니라 뺀다)."""
    if sb.trend_meme_id:
        m = db.get(models.Meme, sb.trend_meme_id)
        if m:
            return {"id": m.id, "name": m.meme_name, "origin": m.origin,
                    "usage_example": m.usage_example}, []
    candidates = (
        db.query(models.Meme)
        .filter(models.Meme.situation != "", models.Meme.situation != "미분류")
        .all()
    )
    return None, [
        {"id": m.id, "name": m.meme_name, "origin": m.origin, "usage_example": m.usage_example}
        for m in candidates
    ]


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
    trend_meme, meme_candidates = _meme_context(sb, db)
    proposed = story_llm.plan_from_text(
        text,
        store={"category": store.category, "address": store.address,
               "hours": store.hours, "desc": store.desc} if store else {},
        char={"name": char.name, "look": char.look, "outfit": char.outfit,
              "desc": char.desc} if char else {},
        ad={"ad_type": ad.ad_type, "ad_concept": ad.ad_concept} if ad else {},
        prods=[{"name": p.name, "qty": p.qty, "date": p.date, "time": p.time,
                "sold_out": p.sold_out} for p in prods],
        current_plan=list(sb.plan or []),
        trend_meme=trend_meme,
        meme_candidates=meme_candidates,
    )
    if proposed is None:
        return _cuts_from_text(text), None
    if not proposed["cuts"]:
        return None
    return proposed["cuts"], proposed["meme_used"]


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
    """사장님이 아무것도 안 적고 대화창의 "스토리 제안받기"를 눌렀을 때 — 자동으로는
    절대 안 뜬다(사장님이 버튼을 눌러야만 부른다). 가게·캐릭터·최근 생산 기록·(있으면)
    밈만으로 스토리를 만든다.
    """
    sb = _get(db)
    _require_character(db)
    text = "(사장님이 따로 말하지 않음 — 가게·캐릭터·최근 생산 기록을 재료로 이야기를 만든다)"
    messages = list(sb.messages or [])
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


def _fill_cuts(indexes: list[int], scenes: list[dict], char_part_text: str, reference: Path) -> None:
    """백그라운드 본체 — 컷마다 프롬프트를 만들고 한 장씩 뽑아 comic_cuts의 칸을 채운다.
    컷 문장의 태그 변환(GPT)도 여기서 한다. 실패한 칸은 failed로 남긴다.
    scenes[i] = {"text": 동작 문장(없으면 대사), "camera": 구도 태그 또는 ""}."""
    for index, scene in zip(indexes, scenes):
        prompt = comic_prompt(char_part_text, scene.get("text", ""), scene.get("camera", ""))
        images = generate_images(prompt, 1, workflow_file=settings.comfy_comic_workflow_file,
                                 reference_path=reference)
        image = images[0] if images else None

        def write(db: Session, index=index, image=image):
            sb = db.get(models.Storyboard, 1)
            if not sb:
                return
            cuts = list(sb.comic_cuts or [])
            if 0 <= index < len(cuts):
                cuts[index] = {**cuts[index], "image": image, "status": "done" if image else "failed"}
                sb.comic_cuts = cuts
                db.commit()

        jobs.with_session(write)


def _start_cuts(sb: models.Storyboard, char: models.Character, indexes: list[int], db: Session) -> None:
    reference = _reference_path(char)
    if reference is None:
        raise HTTPException(400, "캐릭터를 먼저 확정해주세요 — 확정한 캐릭터 그림을 참조로 씁니다")
    cuts = list(sb.comic_cuts or [])
    # 그림엔 대사가 아니라 동작을 넣는다(대사·글자는 말풍선 몫). 동작이 없으면(직접 쓴 컷) 대사 문장을 쓴다.
    scenes = [{"text": cuts[i].get("action") or cuts[i].get("line", ""), "camera": cuts[i].get("camera", "")}
              for i in indexes]
    for i in indexes:
        cuts[i] = {**cuts[i], "image": None, "status": "generating"}
    sb.comic_cuts = cuts
    db.commit()
    # 캐릭터 태그는 여기서 한 번만 계산한다(GPT 1회). 컷 문장 변환은 백그라운드에서.
    # 생김새·옷·나이만 넘긴다 — 성격·능력에서 나오는 표정·소품 태그는 컷마다 정해지는
    # 표정과 부딪친다(chat_ai.COMIC_IDENTITY_FIELDS).
    jobs.submit(_fill_cuts, indexes, scenes, character_part(char, COMIC_IDENTITY_FIELDS), reference)


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
    sb.comic_cuts = [
        {"n": c["n"], "short": c.get("short", ""), "line": c.get("line", ""),
         "action": c.get("action", ""), "camera": c.get("camera", ""),
         "label": f"{c['n']}컷", "image": None, "status": "generating"}
        for c in plan
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


@router.post("/comic/{n}/reroll", response_model=schemas.StoryboardOut)
def reroll_cut(n: int, db: Session = Depends(get_db)):
    """컷 하나만 다시 뽑는다."""
    sb = _get(db)
    cuts = list(sb.comic_cuts or [])
    index = next((i for i, c in enumerate(cuts) if c.get("n") == n), None)
    if index is None:
        raise HTTPException(404, "cut not found")
    char = db.get(models.Character, 1)
    if not char or not char.confirmed:
        raise HTTPException(400, "캐릭터를 먼저 확정해주세요")
    _start_cuts(sb, char, [index], db)
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
