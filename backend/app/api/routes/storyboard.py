"""광고 구성(스토리보드) 대화.

두 가지가 빠져 있다. 의도한 것이다.
- **트렌드 조사**: 제거됐다. 어디서 가져왔는지 댈 수 없는 순위·조회수를 근거로
  사장님에게 광고를 권할 수는 없다.
- **광고 이미지 생성**: 하지 않는다. 그림은 캐릭터 단계에서만 만들고, 여기서는
  그 캐릭터로 무엇을 말할지(컷 구성·대사)만 정한다.

남은 건 전부 사장님이 직접 입력한 값이다. 컷 구성도 템플릿이 아니라 사장님이 쓴
문장을 컷 단위로 쪼갠 것이다 — 서비스가 대신 지어내는 문장은 없다.
"""

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.services.chat_ai import (day_from, fmt_day, is_skip, item_from,
                                  iso_day, new_pid, qty_from, time_from)

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
    return _get(db)


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
    return sb


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
    messages.append({
        "role": "ai", "kind": "text",
        "text": "그대로 둘게요. 어떻게 바꾸면 좋을지 다시 적어주세요.",
    })
    sb.pending = pending
    sb.messages = messages
    db.commit()
    db.refresh(sb)
    return sb
