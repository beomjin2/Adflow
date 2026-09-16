from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=list[schemas.HistoryOut])
def list_history(db: Session = Depends(get_db)):
    return db.query(models.HistoryEntry).order_by(models.HistoryEntry.id.desc()).all()


@router.post("", response_model=schemas.HistoryOut)
def add_history(body: schemas.HistoryCreate, db: Session = Depends(get_db)):
    entry = models.HistoryEntry(**body.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/export")
def export_backup(db: Session = Depends(get_db)):
    """전체 데이터를 JSON 하나로 내보낸다 — frontend의 '백업 파일 내보내기'에 대응."""
    store = db.get(models.Store, 1)
    character = db.get(models.Character, 1)
    ad = db.get(models.AdSettings, 1)
    return {
        "store": schemas.StoreOut.model_validate(store).model_dump() if store else None,
        "character": schemas.CharacterOut.model_validate(character).model_dump() if character else None,
        "ad": schemas.AdOut.model_validate(ad).model_dump() if ad else None,
        "items": [i.name for i in db.query(models.ProductionItem).all()],
        "production_records": [
            schemas.ProductionRecordOut.model_validate(p).model_dump()
            for p in db.query(models.ProductionRecord).all()
        ],
        "history": [
            schemas.HistoryOut.model_validate(h).model_dump()
            for h in db.query(models.HistoryEntry).all()
        ],
    }


@router.post("/import")
def import_backup():
    """백업 복원은 아직 없다. 반쯤 복원해서 데이터를 섞느니 막아두는 편이 낫다."""
    raise HTTPException(501, "백업 불러오기는 아직 준비 중이에요. 내보내기는 지금도 됩니다.")
