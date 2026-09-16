import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

"""가게 정보. 값은 전부 사장님이 직접 입력하거나 올린 것만 들어간다."""

from app import models, schemas
from app.core.database import get_db

router = APIRouter(prefix="/api/store", tags=["store"])

# 저장하려면 이 네 가지는 있어야 한다. 뒤 단계(캐릭터·광고)가 이걸 근거로 돈다.
REQUIRED = {"category": "업종", "address": "주소", "desc": "가게 소개"}

UPLOAD_DIR = "uploads/store"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024


def _get(db: Session) -> models.Store:
    store = db.get(models.Store, 1)
    if not store:
        raise HTTPException(404, "store row missing")
    return store


def _format_hours(store: models.Store) -> str:
    """영업시간 표시 문자열. 시간을 아직 안 고른 상태면 빈 문자열이다 —
    비어 있는데 '연중무휴'라고 적어두면 사장님이 입력한 적 없는 정보가 된다."""
    if not store.open_time or not store.close_time:
        return ""
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
    """저장. 빈 칸이 있으면 무엇이 비었는지 알려주고 저장하지 않는다."""
    store = _get(db)
    missing = [label for field, label in REQUIRED.items() if not (getattr(store, field) or "").strip()]
    if not store.open_time or not store.close_time:
        missing.append("영업시간")
    if missing:
        raise HTTPException(400, f"{' · '.join(missing)}을(를) 채워주세요")
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

    # 라벨은 사장님이 올린 파일 이름 그대로 — 나중에 목록에서 어떤 사진인지 알아본다.
    original = os.path.splitext(os.path.basename(file.filename or ""))[0][:30]
    images = list(store.images or [])
    images.append({
        "label": original or f"사진 {len(images) + 1}",
        "image": f"/api/uploads/store/{filename}",
        "status": "done",
    })
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
