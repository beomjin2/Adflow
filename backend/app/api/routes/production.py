from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db

router = APIRouter(prefix="/api/production", tags=["production"])


# ---------- items ----------
@router.get("/items", response_model=list[schemas.ProductionItemOut])
def list_items(db: Session = Depends(get_db)):
    return db.query(models.ProductionItem).order_by(models.ProductionItem.id).all()


@router.post("/items", response_model=schemas.ProductionItemOut)
def add_item(body: schemas.ProductionItemCreate, db: Session = Depends(get_db)):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "품목 이름을 입력해주세요")
    existing = db.query(models.ProductionItem).filter_by(name=name).first()
    if existing:
        return existing
    item = models.ProductionItem(name=name)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/items/{name}", response_model=schemas.ProductionItemOut)
def rename_item(name: str, body: schemas.ProductionItemCreate, db: Session = Depends(get_db)):
    item = db.query(models.ProductionItem).filter_by(name=name).first()
    if not item:
        raise HTTPException(404, "item not found")
    item.name = body.name.strip()
    db.query(models.ProductionRecord).filter_by(name=name).update({"name": item.name})
    db.commit()
    db.refresh(item)
    return item


@router.delete("/items/{name}", status_code=204)
def delete_item(name: str, db: Session = Depends(get_db)):
    db.query(models.ProductionItem).filter_by(name=name).delete()
    db.commit()


# ---------- records ----------
@router.get("/records", response_model=list[schemas.ProductionRecordOut])
def list_records(db: Session = Depends(get_db)):
    return db.query(models.ProductionRecord).order_by(models.ProductionRecord.id.desc()).all()


@router.post("/records", response_model=schemas.ProductionRecordOut)
def add_record(body: schemas.ProductionRecordCreate, db: Session = Depends(get_db)):
    record = models.ProductionRecord(**body.model_dump())
    db.add(record)
    if not db.query(models.ProductionItem).filter_by(name=record.name).first():
        db.add(models.ProductionItem(name=record.name))
    db.commit()
    db.refresh(record)
    return record


@router.patch("/records/{record_id}", response_model=schemas.ProductionRecordOut)
def patch_record(record_id: int, body: schemas.ProductionRecordPatch, db: Session = Depends(get_db)):
    record = db.get(models.ProductionRecord, record_id)
    if not record:
        raise HTTPException(404, "record not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/records/{record_id}", status_code=204)
def delete_record(record_id: int, db: Session = Depends(get_db)):
    db.query(models.ProductionRecord).filter_by(id=record_id).delete()
    db.commit()
