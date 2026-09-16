import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.services.image_gen import random_hue

router = APIRouter(prefix="/api/store", tags=["store"])

UPLOAD_DIR = "uploads/store"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024


def _get(db: Session) -> models.Store:
    store = db.get(models.Store, 1)
    if not store:
        raise HTTPException(404, "store not seeded")
    return store


def _format_hours(store: models.Store) -> str:
    closed = f"{', '.join(store.closed_days)} 휴무" if store.closed_days else "연중무휴"
    return f"{store.open_time} – {store.close_time}, {closed}"


@router.get("", response_model=schemas.StoreOut)
def get_store(db: Session = Depends(get_db)):
    return _get(db)


@router.put("", response_model=schemas.StoreOut)
def update_store(body: schemas.StoreUpdate, db: Session = Depends(get_db)):
    store = _get(db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(store, field, value)
    store.hours = _format_hours(store)
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


@router.post("/images/upload", response_model=schemas.StoreOut)
async def upload_image(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "이미지 파일만 업로드할 수 있어요")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "파일이 너무 커요 (최대 8MB)")

    store = _get(db)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(os.path.basename(file.filename or ""))[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        ext = ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(UPLOAD_DIR, filename), "wb") as out:
        out.write(content)

    images = list(store.images or [])
    images.append({"label": f"이미지 {len(images) + 1}", "hue": random_hue(), "image": f"/api/uploads/store/{filename}"})
    store.images = images
    db.commit()
    db.refresh(store)
    return store


@router.delete("/images/{index}", response_model=schemas.StoreOut)
def delete_image(index: int, db: Session = Depends(get_db)):
    store = _get(db)
    images = list(store.images or [])
    if not 0 <= index < len(images):
        raise HTTPException(404, "image index out of range")

    removed = images.pop(index)
    image_url = removed.get("image") or ""
    if image_url.startswith("/api/uploads/store/"):
        path = image_url.removeprefix("/api/")
        if os.path.exists(path):
            os.remove(path)

    store.images = images
    db.commit()
    db.refresh(store)
    return store
