"""밈 카드 — 목록과 원문으로부터 카드 만들기.

카드는 서비스 소재다(사장님 데이터가 아님). 만드는 데 GPT 한 번이 들고, 한 번 만들면 저장해 둔다.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.services.meme_ai import make_meme_card

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memes", tags=["memes"])


@router.get("", response_model=list[schemas.MemeCardOut])
def list_memes(db: Session = Depends(get_db)):
    return db.query(models.MemeCard).order_by(models.MemeCard.id).all()


@router.post("", response_model=schemas.MemeCardOut)
def create_meme(body: schemas.MemeCreate, db: Session = Depends(get_db)):
    title = body.title.strip()
    original = body.original.strip()
    if not title:
        raise HTTPException(400, "밈 이름을 적어주세요")
    if len(original) < 40:
        raise HTTPException(400, "밈 원문을 붙여넣어 주세요 — 짧은 요약만으로는 카드가 안 나와요")
    try:
        card = make_meme_card(title, body.source.strip(), original)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception:
        logger.exception("밈 카드 생성 실패")
        raise HTTPException(502, "카드를 만들지 못했어요. 잠시 뒤 다시 시도해 주세요")
    row = models.MemeCard(title=title, source=body.source.strip(), original=original, card=card)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{meme_id}", status_code=204)
def delete_meme(meme_id: int, db: Session = Depends(get_db)):
    row = db.get(models.MemeCard, meme_id)
    if not row:
        raise HTTPException(404, "meme not found")
    db.delete(row)
    db.commit()
