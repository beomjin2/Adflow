"""광고 구성(스토리보드) 대화.

두 가지가 빠져 있다. 의도한 것이다.
- **트렌드 조사**: 제거됐다. 어디서 가져왔는지 댈 수 없는 순위·조회수를 근거로
  사장님에게 광고를 권할 수는 없다.
- **광고 이미지 생성**: 컷 구성이 정해진 뒤 `POST /comic`으로만 만든다(MVP). 확정한
  캐릭터 그림을 참조로 넣어 컷마다 한 장씩 백그라운드에서 그린다. 대사·글자는 그림에
  넣지 않는다 — 그림 모델은 글자를 못 쓴다.

남은 건 전부 사장님이 직접 입력한 값이다. 컷 구성도 템플릿이 아니라 사장님이 쓴
문장을 컷 단위로 쪼갠 것이다 — 서비스가 대신 지어내는 문장은 없다.
"""

import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.config import settings
from app.core.database import get_db
from app.services import jobs
from app.services.chat_ai import (character_part, comic_prompt, comic_prompt_slots, day_from,
                                  fmt_day, is_skip, item_from, iso_day, new_pid, qty_from,
                                  time_from)
from app.services.image_gen import generate_images
from app.services.meme_ai import propose_story

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


def reset_storyboard(db: Session) -> models.Storyboard:
    """광고 설정을 확정했을 때 스토리보드를 처음 상태로 되돌린다."""
    sb = _get(db)
    sb.messages = []
    sb.plan = []
    sb.comic_cuts = []
    sb.prod_logged = False
    sb.pending = {}
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


@router.get("", response_model=schemas.StoryboardOut)
def get_storyboard(db: Session = Depends(get_db)):
    return schemas.storyboard_out(_get(db), jobs.queue_depth())


@router.post("/chat", response_model=schemas.StoryboardOut)
def chat(body: schemas.ChatIn, db: Session = Depends(get_db)):
    """스토리보드 채팅.

    1단계는 생산 기록 받기, 2단계부터는 사장님이 쓴 내용으로 컷 구성을 만든다.
    만든 구성은 바로 반영하지 않고 confirm 카드로 보여준다 — 사장님이 '이렇게
    바뀝니다'를 보고 승인해야 실제로 반영된다.
    """
    sb = _get(db)
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "내용을 입력해주세요")

    messages = list(sb.messages or [])
    messages.append({"role": "me", "kind": "text", "text": text})

    if not sb.prod_logged:
        if is_skip(text):
            messages.append({
                "role": "ai", "kind": "text",
                "text": "알겠어요, 생산 기록은 넘어갈게요. 그럼 광고에 어떤 장면이 들어가면 좋을지 편하게 적어주세요.",
            })
            sb.prod_logged = True
        else:
            name = item_from(text)
            if not name:
                # 못 알아들었으면 기록을 만들지 않는다. 빈 이름으로 저장하면
                # 사장님이 만든 적 없는 생산 기록이 남는다.
                messages.append({
                    "role": "ai", "kind": "text",
                    "text": "품목 이름을 못 알아들었어요. '소금빵 20개'처럼 품목과 수량을 같이 적어주세요. 오늘 만든 게 없으면 '없어요'라고 해주셔도 돼요.",
                })
            else:
                day = day_from(text)
                record = models.ProductionRecord(
                    name=name, qty=qty_from(text), date=day,
                    time=time_from(text), sold_out="",
                )
                db.add(record)
                db.flush()
                if not db.query(models.ProductionItem).filter_by(name=name).first():
                    db.add(models.ProductionItem(name=name))
                today = "(오늘)" if day == iso_day(0) else ""
                messages.append({
                    "role": "ai", "kind": "text",
                    "text": f"'{name}' 생산 기록을 {fmt_day(day)}{today}로 남겼어요. 다르면 아래에서 바로 고쳐주세요.",
                })
                messages.append({"role": "ai", "kind": "prod", "prodId": record.id})
                messages.append({
                    "role": "ai", "kind": "text",
                    "text": f"그럼 {name} 이야기로 광고를 만들어볼까요? 어떤 장면이 들어가면 좋을지 적어주세요 — 문장 하나가 한 컷이 돼요.",
                })
                sb.prod_logged = True
    else:
        cuts = _cuts_from_text(text)
        if not cuts:
            messages.append({
                "role": "ai", "kind": "text",
                "text": "어떤 장면인지 한 문장으로 적어주세요. 문장 하나가 한 컷이 돼요.",
            })
        else:
            current = list(sb.plan or [])
            diffs = []
            for cut in cuts:
                before = next((c["line"] for c in current if c.get("n") == cut["n"]), "아직 없음")
                diffs.append({"label": f"{cut['n']}컷", "from": before, "to": cut["line"]})
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
    scenes[i] = {"slots": 팀장 시트의 컷 슬롯} 또는 옛 형식 {"text": 동작 문장, "camera": 구도 태그}.
    슬롯이 있으면 comic_prompt_slots로, 없으면(직접 쓴 옛 컷) 옛 경로로 조립한다."""
    for index, scene in zip(indexes, scenes):
        trace = None
        position = None
        if scene.get("slots"):
            prompt, trace = comic_prompt_slots(char_part_text, scene["slots"])
            position = (scene["slots"].get("shot") or {}).get("position")   # 왼쪽·가운데·오른쪽 → 넓게 뽑아 자름
        else:
            prompt = comic_prompt(char_part_text, scene.get("text", ""), scene.get("camera", ""))
        images = generate_images(prompt, 1, workflow_file=settings.comfy_comic_workflow_file,
                                 reference_path=reference, position=position)
        image = images[0] if images else None

        def write(db: Session, index=index, image=image, prompt=prompt, trace=trace):
            sb = db.get(models.Storyboard, 1)
            if not sb:
                return
            cuts = list(sb.comic_cuts or [])
            if 0 <= index < len(cuts):
                # 프롬프트와 슬롯→태그 기록을 컷에 남긴다 — 화면·보고서에서 "왜 이렇게 나왔나"를 보여주려고.
                cuts[index] = {**cuts[index], "image": image, "status": "done" if image else "failed",
                               "prompt": prompt, "trace": trace}
                sb.comic_cuts = cuts
                db.commit()

        jobs.with_session(write)


def _start_cuts(sb: models.Storyboard, char: models.Character, indexes: list[int], db: Session) -> None:
    reference = _reference_path(char)
    if reference is None:
        raise HTTPException(400, "캐릭터를 먼저 확정해주세요 — 확정한 캐릭터 그림을 참조로 씁니다")
    cuts = list(sb.comic_cuts or [])
    # 그림엔 대사가 아니라 동작을 넣는다(대사·글자는 말풍선 몫). 슬롯이 있으면 슬롯으로,
    # 없으면(직접 쓴 옛 컷) 동작 문장 → 그것도 없으면 대사 문장을 쓴다.
    scenes = [
        {"slots": cuts[i]["slots"]} if cuts[i].get("slots")
        else {"text": cuts[i].get("action") or cuts[i].get("line", ""), "camera": cuts[i].get("camera", "")}
        for i in indexes
    ]
    for i in indexes:
        cuts[i] = {**cuts[i], "image": None, "status": "generating"}
    sb.comic_cuts = cuts
    db.commit()
    # 캐릭터 태그는 여기서 한 번만 계산한다(GPT 1회). 컷 문장 변환은 백그라운드에서.
    jobs.submit(_fill_cuts, indexes, scenes, character_part(char), reference)


@router.post("/propose", response_model=schemas.StoryboardOut)
def propose(body: schemas.ProposeIn, db: Session = Depends(get_db)):
    """밈 카드 + 가게 정보로 GPT가 4컷 초안을 만든다.

    바로 확정하지 않는다 — 기존 확인 카드(pending/plan)로 제안하고, 사장님이 "이대로
    바꾸기"를 눌러야 컷 구성이 된다. 서비스가 문장을 지어내는 유일한 지점이라 확인을 거친다.
    """
    sb = _get(db)
    meme = db.get(models.MemeCard, body.meme_id)
    if not meme:
        raise HTTPException(404, "밈 카드를 찾을 수 없어요")
    store = db.get(models.Store, 1)
    ad = db.get(models.AdSettings, 1)
    char = db.get(models.Character, 1)
    prods = db.query(models.ProductionRecord).order_by(models.ProductionRecord.id.desc()).limit(10).all()
    try:
        story = propose_story(
            meme.card or {}, meme.title,
            {"category": store.category, "address": store.address, "hours": store.hours, "desc": store.desc} if store else {},
            [{"name": p.name, "qty": p.qty, "date": p.date, "time": p.time, "sold_out": p.sold_out} for p in prods],
            {"ad_type": ad.ad_type, "ad_concept": ad.ad_concept} if ad else {},
            # 마스코트 시트 전부 — 작가 GPT가 말투를 여기서 뽑는다(전엔 이름만 보내 목소리가 없었다)
            {"name": char.name, "age": char.age, "gender": char.gender, "desc": char.desc, "hobby": char.hobby,
             "abilities": char.abilities, "keywords": list(char.keywords or [])} if char else {},
        )
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception:
        logger.exception("스토리 제안 실패")
        raise HTTPException(502, "스토리를 만들지 못했어요. 잠시 뒤 다시 시도해 주세요")

    cuts = story["cuts"]
    current = list(sb.plan or [])
    diffs = []
    for cut in cuts:
        before = next((c["line"] for c in current if c.get("n") == cut["n"]), "아직 없음")
        diffs.append({"label": f"{cut['n']}컷", "from": before, "to": f"{cut['line']} — {cut.get('action', '')}"})
    for old in current[len(cuts):]:
        diffs.append({"label": f"{old['n']}컷", "from": old["line"], "to": "삭제"})

    pending = dict(sb.pending or {})
    pid = new_pid()
    pending[pid] = {"which": "sb", "kind": "plan", "diffs": diffs, "payload": {"plan": cuts}, "status": "open"}
    messages = list(sb.messages or [])
    messages.append({
        "role": "ai", "kind": "text",
        "text": f"'{meme.title}' 밈으로 '{story['title']}' 4컷을 제안해요. 마음에 들면 아래에서 이대로 바꾸기를 눌러주세요.",
    })
    messages.append({"role": "ai", "kind": "confirm", "pid": pid})
    sb.pending = pending
    sb.messages = messages
    sb.prod_logged = True  # 제안을 받은 뒤의 채팅은 컷 수정으로 다룬다(생산 기록 질문 단계 건너뜀)
    db.commit()
    db.refresh(sb)
    return schemas.storyboard_out(sb, jobs.queue_depth())


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
         "slots": c.get("slots"),   # 팀장 시트의 컷 슬롯. 옛 plan엔 없다(→ 옛 경로)
         "caption": c.get("caption", ""),   # 그림 아래 캡션(가게 정보)
         "label": f"{c['n']}컷", "image": None, "status": "generating"}
        for c in plan
    ]
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
