#!/usr/bin/env python3
"""crawling/memes_nested.json(+ memes_classified.json)을 memes 테이블에 옮긴다.

    cd backend && .venv/Scripts/python.exe import_memes.py

memes_nested.json은 밈 1건 = 객체 1개로, 하위 테이블(링크·트렌드 검색어·이미지)을
그 안에 중첩해 담은 v3 포맷이다. links/trend_terms/card/trend/examples/full_text는
지금 화면 어디서도 안 읽어서 DB로 안 옮긴다 — card/trend/examples/full_text는
_meta.empty_yet에 적힌 대로 아직 전부 비어 있고(다음 크롤링에서 채워지면 그때 컬럼을
추가한다), links/trend_terms는 실제 값이 있지만 아직 쓸 데가 없다.

image는 크롤러 쪽 파일명(예: gogumafarm_대박삐_02.jpg)을 기대하지만 실제로 받아둔
사본은 crawling/images/meme-01.jpg~25.jpg라 이름이 다르다 — bytes_len(파일 크기)으로
실제 파일을 찾아 image.served_path에 적어둔 걸 그대로 쓴다(이 파일에 이미 한 번
써놨다, 지운 채로 다시 받으면 이 스크립트가 다시 못 찾으니 served_path는 유지할 것).
같은 밈이 사이트마다 다르게 표현돼도(canonical_id) 대표 쪽 이미지를 그대로 쓴다.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows cp949 콘솔에서 한글 출력 시 깨지는 것 방지

from app import models
from app.core.database import SessionLocal, init_db

CRAWLING_DIR = Path(__file__).resolve().parents[1] / "crawling"
NESTED_PATH = CRAWLING_DIR / "memes_nested.json"
CLASSIFIED_PATH = CRAWLING_DIR / "memes_classified.json"


def _load_classification() -> dict:
    if not CLASSIFIED_PATH.exists():
        return {}
    items = json.loads(CLASSIFIED_PATH.read_text(encoding="utf-8"))
    return {item["unique_id"]: item for item in items}


def main() -> None:
    init_db()
    data = json.loads(NESTED_PATH.read_text(encoding="utf-8"))
    memes_by_id = {m["id"]: m for m in data["memes"]}
    classified = _load_classification()

    db = SessionLocal()
    inserted = updated = missing_image = 0
    try:
        for item in data["memes"]:
            canon = memes_by_id.get(item["canonical_id"]) or item
            image = ((canon.get("image") or {}).get("served_path")) or ""
            if not image:
                missing_image += 1

            classification = classified.get(item["id"], {})
            fields = dict(
                id=item["id"],
                source=item.get("source") or "",
                url=item.get("url") or "",
                meme_name=item.get("name") or "",
                origin=item.get("origin") or "",
                usage_example=item.get("usage_example") or "",
                published_date=item.get("published_date") or "",
                views=item.get("views"),
                rank_in_source=item.get("rank_in_source"),
                canonical_id=item.get("canonical_id") or item["id"],
                first_seen_at=item.get("first_seen_at") or "",
                last_seen_at=item.get("last_seen_at") or "",
                image=image,
                situation=classification.get("situation") or "",
                situation_score=classification.get("situation_score"),
                ad_safe=classification.get("ad_safe"),
            )
            row = db.get(models.Meme, fields["id"])
            if row is None:
                db.add(models.Meme(**fields))
                inserted += 1
            else:
                for key, value in fields.items():
                    setattr(row, key, value)
                updated += 1
        db.commit()
    finally:
        db.close()

    print(f"{NESTED_PATH.name}: {len(data['memes'])}건")
    print(f"완료 — 새로 추가 {inserted}건, 갱신 {updated}건, 이미지 없음 {missing_image}건")


if __name__ == "__main__":
    main()
