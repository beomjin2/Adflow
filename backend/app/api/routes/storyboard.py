from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.services.chat_ai import (day_from, is_skip, item_from, fmt_day,
                                   iso_day, new_pid, qty_from, time_from)
from app.services.image_gen import random_hue
from app.services.trend_data import BASE_PLAN

router = APIRouter(prefix="/api/storyboard", tags=["storyboard"])


def _get(db: Session) -> models.Storyboard:
    sb = db.get(models.Storyboard, 1)
    if not sb:
        raise HTTPException(404, "storyboard not seeded")
    return sb


def reset_storyboard(db: Session, with_trend: bool, trend_pick: str = "") -> models.Storyboard:
    sb = _get(db)
    text = (
        f"이 트렌드로 광고를 만들어볼게요. 먼저 — 오늘 생산한 품목이 있나요? 품목 이름과 수량을 말해주면 생산 기록으로 남겨둘게요."
        if with_trend else
        "광고를 만들기 전에 하나만요 — 오늘 생산한 품목이 있나요? 품목 이름과 수량을 말해주면 생산 기록으로 남겨둘게요."
    )
    sb.messages = [{"role": "ai", "kind": "text", "text": text}]
    sb.plan = []
    sb.comic_cuts = []
    sb.prod_logged = False
    db.commit()
    db.refresh(sb)
    return sb


@router.get("", response_model=schemas.StoryboardOut)
def get_storyboard(db: Session = Depends(get_db)):
    return _get(db)


@router.post("/chat", response_model=schemas.StoryboardOut)
def chat(body: schemas.ChatIn, ad_type: str = "인스타 게시물",
         trend_applied: bool = False, trend_pick: str = "",
         db: Session = Depends(get_db)):
    """스토리보드 채팅 — 생산기록 자동수집 후 플랜/네컷만화를 제안한다.
    ad_type/trend_applied/trend_pick은 프론트가 현재 광고 설정을 함께 보내준다."""
    sb = _get(db)
    messages = list(sb.messages or [])
    messages.append({"role": "me", "kind": "text", "text": body.text})

    if not sb.prod_logged:
        if is_skip(body.text):
            messages.append({"role": "ai", "kind": "text", "text": "알겠어요, 생산 기록은 넘어갈게요. 그럼 어떤 이야기로 광고를 만들까요?"})
            sb.prod_logged = True
        else:
            name = item_from(body.text)
            qty = qty_from(body.text)
            day = day_from(body.text)
            is_today = day == iso_day(0)
            record = models.ProductionRecord(name=name, qty=qty, date=day, time=time_from(body.text), sold_out="")
            db.add(record)
            db.flush()
            if not db.query(models.ProductionItem).filter_by(name=name).first():
                db.add(models.ProductionItem(name=name))
            messages.append({
                "role": "ai", "kind": "text",
                "text": f"'{name}' 생산 기록을 {fmt_day(day)}{'(오늘)' if is_today else ''}로 남겼어요. 다르면 아래에서 바로 고쳐주세요. 매진 시각을 비워두면 알림으로 다시 물어볼게요.",
            })
            messages.append({"role": "ai", "kind": "prod", "prodId": record.id})
            messages.append({"role": "ai", "kind": "text", "text": f"그럼 {name} 이야기로 광고를 만들어볼까요? 알리고 싶은 걸 말해주세요."})
            sb.prod_logged = True
    else:
        plan = list(sb.plan or [])
        comic_cuts = list(sb.comic_cuts or [])
        pending = dict(sb.pending or {})
        if not plan:
            new_plan = [dict(c) for c in BASE_PLAN]
            if trend_applied:
                new_plan[2] = {**new_plan[2], "line": f"'{trend_pick}' 밈을 그대로 따라 하는 손님 리액션 컷."}
            diffs = [{"label": f"{c['n']}컷", "from": "아직 없음", "to": c["line"]} for c in new_plan]
            pid = new_pid()
            pending[pid] = {"which": "sb", "kind": "plan", "diffs": diffs, "payload": {"plan": new_plan}, "status": "open"}
            messages.append({"role": "ai", "kind": "confirm", "pid": pid})
        elif not comic_cuts:
            next_line = "손님이 소금빵을 들고 과장되게 놀라는 컷 — 효과선 추가."
            new_plan = [{**c, "line": next_line} if c["n"] == 3 else c for c in plan]
            prev = plan[2]["line"] if len(plan) > 2 else "없음"
            diffs = [{"label": "3컷", "from": prev, "to": next_line}]
            pid = new_pid()
            pending[pid] = {"which": "sb", "kind": "plan", "diffs": diffs, "payload": {"plan": new_plan}, "status": "open"}
            messages.append({"role": "ai", "kind": "confirm", "pid": pid})
        else:
            new_cuts = [{**c, "hue": random_hue()} if c["n"] == 2 else c for c in comic_cuts]
            diffs = [{"label": "2컷 그림", "from": "지금 그림", "to": "새로 뽑은 그림"}]
            pid = new_pid()
            pending[pid] = {"which": "sb", "kind": "comic", "diffs": diffs, "payload": {"cuts": new_cuts}, "status": "open"}
            messages.append({"role": "ai", "kind": "confirm", "pid": pid})
        sb.pending = pending

    sb.messages = messages
    db.commit()
    db.refresh(sb)
    return sb


@router.post("/confirm/{pid}", response_model=schemas.StoryboardOut)
def confirm_pending(pid: str, db: Session = Depends(get_db)):
    sb = _get(db)
    pending = dict(sb.pending or {})
    p = pending.get(pid)
    if not p:
        raise HTTPException(404, "pending not found")
    p = {**p, "status": "applied"}
    pending[pid] = p
    messages = list(sb.messages or [])
    if p["kind"] == "plan":
        sb.plan = p["payload"]["plan"]
        messages.append({"role": "ai", "kind": "plan", "ref": "plan"})
    elif p["kind"] == "comic":
        sb.comic_cuts = p["payload"]["cuts"]
        messages.append({"role": "ai", "kind": "comic", "ref": "comic"})
    sb.pending = pending
    sb.messages = messages
    db.commit()
    db.refresh(sb)
    return sb


@router.post("/decline/{pid}", response_model=schemas.StoryboardOut)
def decline_pending(pid: str, db: Session = Depends(get_db)):
    sb = _get(db)
    pending = dict(sb.pending or {})
    p = pending.get(pid)
    if not p or p.get("status") != "open":
        raise HTTPException(404, "pending not open")
    pending[pid] = {**p, "status": "declined"}
    messages = list(sb.messages or [])
    messages.append({"role": "ai", "kind": "text", "text": "그대로 둘게요. 어떻게 바꾸면 좋을지 말해주세요."})
    sb.pending = pending
    sb.messages = messages
    db.commit()
    db.refresh(sb)
    return sb


@router.post("/comic", response_model=schemas.StoryboardOut)
def make_comic(db: Session = Depends(get_db)):
    sb = _get(db)
    if not sb.plan:
        raise HTTPException(400, "먼저 대화로 플랜을 만들어주세요")
    base = random_hue()
    cuts = [{"n": c["n"], "short": c["short"], "line": c["line"], "hue": (base + i * 26) % 360}
            for i, c in enumerate(sb.plan)]
    existed = bool(sb.comic_cuts)
    diffs = [{"label": f"{c['n']}컷", "from": "지금 그림" if existed else "아직 없음", "to": c["line"]} for c in cuts]
    pending = dict(sb.pending or {})
    pid = new_pid()
    pending[pid] = {"which": "sb", "kind": "comic", "diffs": diffs, "payload": {"cuts": cuts}, "status": "open"}
    sb.pending = pending
    messages = list(sb.messages or [])
    messages.append({"role": "ai", "kind": "confirm", "pid": pid})
    sb.messages = messages
    db.commit()
    db.refresh(sb)
    return sb


@router.post("/cuts/{n}/reroll", response_model=schemas.StoryboardOut)
def reroll_cut(n: int, db: Session = Depends(get_db)):
    sb = _get(db)
    cuts = list(sb.comic_cuts or [])
    sb.comic_cuts = [{**c, "hue": random_hue()} if c["n"] == n else c for c in cuts]
    db.commit()
    db.refresh(sb)
    return sb
