#!/usr/bin/env python3
"""meam/*.json 원본 3개를 memes 테이블에 그대로 옮겨 담는다.

    cd backend && .venv/bin/python import_memes.py

이미 있는 id는 덮어쓴다(재실행해도 안전). 소스별로 컬럼 구성이 달라서 스키마는
app/models.py의 Meme를 참고 — 한 소스에만 있는 필드는 다른 소스 행에서 빈 값으로 남는다.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows cp949 콘솔에서 한글/em-dash 출력 시 깨지는 것 방지

from app import models
from app.core.database import SessionLocal, init_db

MEAM_DIR = Path(__file__).resolve().parents[1] / "meam"


def _from_gogumafarm(item: dict) -> dict:
    return dict(
        id=item["id"],
        source=item.get("source") or "gogumafarm",
        url=item.get("url") or "",
        meme_name=item.get("meme_name") or "",
        origin=item.get("origin") or "",
        image=item.get("image") or "",
        description=item.get("description") or "",
        images=item.get("images") or [],
        tags=item.get("tags") or [],
        published_date=item.get("published_date") or "",
        from_article=item.get("_from_article") or "",
    )


def _from_wepick(item: dict) -> dict:
    return dict(
        id=item["id"],
        source=item.get("source") or "wepick_memepedia",
        url=item.get("url") or "",
        meme_name=item.get("meme_name") or "",
        origin=item.get("origin") or "",
        image=item.get("image") or "",
        description=item.get("description") or "",
        images=item.get("images") or [],
        tags=item.get("tags") or [],
        published_date=item.get("published_date") or "",
        category=item.get("category") or "",
        author=item.get("author") or "",
        view_count=item.get("view_count") or "",
        videos=item.get("videos") or [],
        article_title=item.get("article_title") or "",
        collection_number=item.get("_collection_number") or "",
        usage_source=item.get("_usage_source") or "",
    )


def _from_maily(item: dict) -> dict:
    return dict(
        id=item["post_id"],
        source="maily_trendaword",
        url=item.get("url") or "",
        meme_name=item.get("meme_name") or "",
        origin=item.get("origin") or "",
        image=item.get("image") or "",
        title=item.get("title") or "",
        subtitle=item.get("subtitle") or "",
        published_at=item.get("published_at") or "",
        thumbnail=item.get("thumbnail") or "",
        image_from=item.get("image_from") or "",
        origin_mode=item.get("origin_mode") or "",
        usage=item.get("usage") or "",
        views=item.get("views") or "",
        image_fix_note=item.get("image_fix_note") or "",
    )


SOURCES = [
    ("gogumafarm_raw.json", _from_gogumafarm),
    ("maily_trendaword_raw.json", _from_maily),
    ("wepick_memepedia_raw.json", _from_wepick),
]


def main() -> None:
    init_db()
    db = SessionLocal()
    inserted = updated = 0
    try:
        for filename, convert in SOURCES:
            path = MEAM_DIR / filename
            items = json.loads(path.read_text(encoding="utf-8"))
            for raw in items:
                fields = convert(raw)
                row = db.get(models.Meme, fields["id"])
                if row is None:
                    db.add(models.Meme(**fields))
                    inserted += 1
                else:
                    for key, value in fields.items():
                        setattr(row, key, value)
                    updated += 1
            print(f"{filename}: {len(items)}건")
        db.commit()
    finally:
        db.close()
    print(f"완료 — 새로 추가 {inserted}건, 갱신 {updated}건")


if __name__ == "__main__":
    main()
