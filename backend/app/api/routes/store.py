import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.config import STORE_MAX_IMAGES
from app.core.database import get_db
from app.services.image_gen import random_hue

router = APIRouter(prefix="/api/store", tags=["store"])

UPLOAD_DIR = "uploads/store"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def _get(db: Session) -> models.Store:
    store = db.get(models.Store, 1)
    if not store:
        raise HTTPException(404, "store not seeded")
    return store


def _format_hours(store: models.Store) -> str:
    closed = f"{', '.join(store.closed_days)} 휴무" if store.closed_days else "연중무휴"
    if not store.open_time or not store.close_time:
        return f"영업시간 미정, {closed}"
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
    store = _get(db)
    if len(store.images or []) >= STORE_MAX_IMAGES:
        raise HTTPException(400, f"이미지는 최대 {STORE_MAX_IMAGES}장까지 올릴 수 있어요")
    ext = os.path.splitext(os.path.basename(file.filename or ""))[1].lower()
    if not (file.content_type or "").startswith("image/") or ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "jpg, png, webp 파일만 업로드할 수 있어요")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "파일이 너무 커요 (최대 5MB)")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(UPLOAD_DIR, filename), "wb") as out:
        out.write(content)

    # 파일 저장 중 다른 요청이 images를 바꿨을 수 있으니, 쓰기 직전에 최신 상태를 다시 읽는다.
    db.refresh(store)
    images = list(store.images or [])
    if len(images) >= STORE_MAX_IMAGES:
        os.remove(os.path.join(UPLOAD_DIR, filename))
        raise HTTPException(400, f"이미지는 최대 {STORE_MAX_IMAGES}장까지 올릴 수 있어요")
    images.append({"label": f"이미지 {len(images) + 1}", "hue": random_hue(), "image": f"/api/uploads/store/{filename}"})
    store.images = images
    db.commit()
    db.refresh(store)
    return store


@router.delete("/images/{index}", response_model=schemas.StoreOut)
def delete_image(index: int, db: Session = Depends(get_db)):
    store = _get(db)
    db.refresh(store)
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
