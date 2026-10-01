"""서비스를 처음 쓰는 상태로 되돌린다 — 내 정보 > 백업 · 초기화 탭의 "처음 상태로 초기화" 버튼이 부른다.

VM 에서 사람이 돌리던 `deploy/reset_service_data.py` 와 같은 범위를 지운다. 사장님이 다시
해 보고 싶을 때마다 누가 서버에 들어가 스크립트를 돌려 줘야 했는데, 그걸 화면에서 직접 하게 한다.

지우는 것
  - 가게 정보(store 1번 행) — 값만 비운다. 올린 사진은 지우지 않고 uploads/_removed-<날짜>/ 로 옮긴다.
  - 캐릭터(character 1번 행) — `POST /api/character/reset` 과 같은 함수로 비운다.
  - 광고 설정(ad_settings 1번 행)
  - 광고 대화·컷 구성·네컷(storyboard 1번 행) — 트렌드에서 골라 둔 밈까지 푼다.
  - 생산 기록·품목·보관한 광고 — 행을 전부 지운다. 지운 뒤 id 가 1부터 다시 시작한다.

남기는 것
  - 마스코트 보관소(mascots) — 공들여 만든 그림이라 한 번에 날리지 않는다. 보관소에서 한 장씩 지운다.
  - 트렌드 밈(memes) — 크롤링이 채우는 자료지 사장님이 만든 게 아니다.
  - 그려둔 그림 파일(media/) — 참조만 끊는다. 캐릭터·스토리보드 reset 과 같은 판단이다.

싱글턴 행은 지우지 않고 값만 비운다. 행이 없으면 라우터가 `db.get(..., 1)` 에서 404 를 낸다.
"""

from __future__ import annotations

import datetime as dt
import os
import shutil

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models
from app.api.routes.character import reset_character
from app.api.routes.storyboard import reset_storyboard
from app.core.config import settings
from app.core.database import get_db

router = APIRouter(prefix="/api", tags=["reset"])

# 통째로 비우는 표. 여기 든 행은 전부 사장님이 쓰는 동안 쌓인 것이다.
EMPTY_TABLES = (models.ProductionRecord, models.ProductionItem, models.HistoryEntry)


def _move_store_photos(images: list) -> int:
    """store.images 가 가리키는 업로드 파일을 uploads/_removed-<날짜>/ 로 옮긴다.

    지우지 않고 옮긴다 — 진짜 가게 사진이 섞여 있으면 되돌릴 수 있어야 한다
    (deploy/reset_service_data.py 와 같은 판단). 경로는 URL 에서 파일명만 떼어 settings
    기준으로 다시 만든다(store 라우터의 delete_image 와 같은 이유).
    """
    names = []
    for item in images or []:
        url = (item or {}).get("image") or ""
        if url.startswith("/api/uploads/store/"):
            names.append(os.path.basename(url))
    if not names:
        return 0

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = settings.uploads_path.parent / f"_removed-{stamp}"
    dest.mkdir(parents=True, exist_ok=True)
    moved = 0
    for name in names:
        src = settings.uploads_path / name
        if src.exists():
            shutil.move(str(src), str(dest / name))
            moved += 1
    return moved


def _restart_ids(db: Session) -> None:
    """지운 표의 id 가 1부터 다시 시작하게 한다. 남겨두면 첫 기록이 51번으로 생긴다.

    sqlite 전용이다(autoincrement 카운터가 sqlite_sequence 에 산다). 다른 DB 면 그냥 둔다 —
    id 가 이어지는 건 보기 안 좋을 뿐 동작엔 지장이 없다.
    """
    if db.get_bind().dialect.name != "sqlite":
        return
    has_seq = db.execute(
        text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_sequence'")
    ).first()
    if not has_seq:
        return
    for model in EMPTY_TABLES:
        db.execute(text("DELETE FROM sqlite_sequence WHERE name = :name"), {"name": model.__tablename__})


@router.post("/reset")
def reset_all(db: Session = Depends(get_db)):
    """전부 처음 상태로. 되돌릴 수 없으니 화면이 한 번 더 묻고 부른다.

    돌려주는 값은 무엇을 얼마나 지웠는지다 — 화면은 이걸 보여주지 않고 새로고침하지만,
    로그·확인용으로 남긴다.
    """
    cleared: dict[str, int] = {}

    store = db.get(models.Store, 1)
    if store:
        cleared["store_photos_moved"] = _move_store_photos(list(store.images or []))
        store.saved = False
        store.category = ""
        store.address = ""
        store.hours = ""
        store.open_time = ""
        store.close_time = ""
        store.closed_days = []
        store.desc = ""
        store.images = []

    ad = db.get(models.AdSettings, 1)
    if ad:
        ad.ad_type = ""
        ad.ad_concept = ""

    for model in EMPTY_TABLES:
        cleared[model.__tablename__] = db.query(model).delete()
    _restart_ids(db)
    db.commit()

    # 캐릭터·스토리보드는 각자의 reset 라우트와 **같은 함수**로 비운다. 지우는 범위를 여기서
    # 따로 적으면 그쪽에 칸이 하나 늘 때 여기만 빠진다. 둘 다 안에서 commit 한다.
    reset_character(db)
    reset_storyboard(db, None)

    return {"ok": True, "cleared": cleared}
