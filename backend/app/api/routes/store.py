from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.services.image_gen import random_hue

router = APIRouter(prefix="/api/store", tags=["store"])


def _get(db: Session) -> models.Store:
    store = db.get(models.Store, 1)
    if not store:
        raise HTTPException(404, "store not seeded")
    return store


@router.get("", response_model=schemas.StoreOut)
def get_store(db: Session = Depends(get_db)):
    return _get(db)


@router.put("", response_model=schemas.StoreOut)
def update_store(body: schemas.StoreUpdate, db: Session = Depends(get_db)):
    store = _get(db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(store, field, value)
    db.commit()
    db.refresh(store)
    return store


@router.post("/save", response_model=schemas.StoreOut)
def save_store(db: Session = Depends(get_db)):
    store = _get(db)
    store.saved = True
    db.commit()
    db.refresh(store)
    return store


@router.post("/images", response_model=schemas.StoreOut)
def add_image(db: Session = Depends(get_db)):
    store = _get(db)
    images = list(store.images or [])
    images.append({"label": f"이미지 {len(images) + 1}", "hue": random_hue()})
    store.images = images
    db.commit()
    db.refresh(store)
    return store


@router.post("/images/{index}/reroll", response_model=schemas.StoreOut)
def reroll_image(index: int, db: Session = Depends(get_db)):
    store = _get(db)
    images = list(store.images or [])
    if not 0 <= index < len(images):
        raise HTTPException(404, "image index out of range")
    images[index] = {**images[index], "hue": random_hue()}
    store.images = images
    db.commit()
    db.refresh(store)
    return store
