#!/usr/bin/env python3
"""crawling/memes_all.json(+ memes_classified.json)을 memes 테이블에 옮긴다.

    cd backend && .venv/Scripts/python.exe import_memes.py

memes_all.json은 밈 1건 = 객체 1개, 사이트 간 중복은 이미 merged_from으로 합쳐진
포맷이다. card는 _meta.images 설명대로 아직 항상 비어 있어 DB로 안 옮긴다.

id/image.file이 고구마팜 항목 일부에서 한글로 돼 있는데(예: "gogumafarm_대박삐_02"),
실제로 받아둔 이미지 사본은 로마자 파일명이다(예: gogumafarm_daebakppi_02.jpg) — 정확한
경로로 못 찾으면 같은 소스(gogumafarm) 안에서 id 끝의 일련번호(_02, _09 같은 두 자리
숫자)로 실제 파일을 찾는다. memes_classified.json의 unique_id도 같은 이유로 로마자라
분류 결과를 붙일 때 이 일련번호 매칭을 그대로 재사용한다.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows cp949 콘솔에서 한글 출력 시 깨지는 것 방지

from app import models
from app.core.database import SessionLocal, init_db

CRAWLING_DIR = Path(__file__).resolve().parents[1] / "crawling"
IMAGES_DIR = CRAWLING_DIR / "images"
ALL_PATH = CRAWLING_DIR / "memes_all.json"
CLASSIFIED_PATH = CRAWLING_DIR / "memes_classified.json"

_SUFFIX_RE = re.compile(r"_(\d{2})$")
_IMAGE_SUFFIX_RE = re.compile(r"^gogumafarm_[a-z]+_(\d{2})\.jpg$")


def _suffix(item_id: str) -> str | None:
    m = _SUFFIX_RE.search(item_id)
    return m.group(1) if m else None


def _load_classification() -> dict:
    if not CLASSIFIED_PATH.exists():
        return {}
    items = json.loads(CLASSIFIED_PATH.read_text(encoding="utf-8"))
    return {item["unique_id"]: item for item in items}


def _gogumafarm_suffix_index(ids: list[str]) -> dict[str, str]:
    """gogumafarm 소스의 로마자 문자열(unique_id 또는 실제 파일명)을 일련번호로 색인한다."""
    index: dict[str, str] = {}
    for value in ids:
        m = _SUFFIX_RE.search(value)
        if m:
            index[m.group(1)] = value
    return index


def _resolve_image(item: dict, image_suffix_index: dict[str, str]) -> str:
    file_field = ((item.get("image") or {}).get("file")) or ""
    name = Path(file_field).name if file_field else ""
    if name and (IMAGES_DIR / name).exists():
        return name
    if item.get("source") == "gogumafarm":
        suf = _suffix(item["id"])
        if suf and suf in image_suffix_index:
            return image_suffix_index[suf]
    return ""


def _resolve_classification(item: dict, classified_by_id: dict, classified_suffix_index: dict[str, str]) -> dict:
    hit = classified_by_id.get(item["id"])
    if hit:
        return hit
    if item.get("source") == "gogumafarm":
        suf = _suffix(item["id"])
        uid = classified_suffix_index.get(suf) if suf else None
        if uid:
            return classified_by_id.get(uid, {})
    return {}


def main() -> None:
    init_db()
    data = json.loads(ALL_PATH.read_text(encoding="utf-8"))
    memes = data["memes"]

    classified_by_id = _load_classification()
    classified_suffix_index = _gogumafarm_suffix_index(
        [uid for uid in classified_by_id if uid.startswith("gogumafarm_")]
    )
    image_suffix_index: dict[str, str] = {}
    for f in IMAGES_DIR.glob("gogumafarm_*.jpg"):
        m = _IMAGE_SUFFIX_RE.match(f.name)
        if m:
            image_suffix_index[m.group(1)] = f.name

    db = SessionLocal()
    inserted = updated = missing_image = 0
    try:
        for item in memes:
            image_name = _resolve_image(item, image_suffix_index)
            if not image_name:
                missing_image += 1
            image = f"/api/meme-images/{image_name}" if image_name else ""

            classification = _resolve_classification(item, classified_by_id, classified_suffix_index)
            trend = item.get("trend") or {}
            fields = dict(
                id=item["id"],
                source=item.get("source") or "",
                source_label=item.get("source_label") or "",
                url=item.get("url") or "",
                meme_name=item.get("name") or "",
                origin=item.get("origin") or "",
                usage_example=item.get("usage_example") or "",
                published_date=item.get("published_date") or "",
                views=item.get("views"),
                rank_in_source=item.get("rank_in_source"),
                image=image,
                period_start=trend.get("period_start") or "",
                period_end=trend.get("period_end") or "",
                peak_date=trend.get("peak_date") or "",
                trend_method=trend.get("method") or "",
                pre_existing=trend.get("pre_existing"),
                blog_total=trend.get("blog_total"),
                search_terms=item.get("search_terms") or [],
                links=item.get("links") or [],
                merged_from=item.get("merged_from") or [],
            )
            # 분류 결과는 파일이 있을 때만 덮어쓴다.
            # classify_memes_situation.py가 memes 테이블을 직접 읽는 방식으로 바뀌면서
            # memes_classified.json은 더 이상 저장소에 없다(커밋 cd2b386). 그 상태로 여기서
            # ""를 밀어 넣으면 DB에 이미 들어 있는 분류가 통째로 지워진다.
            if classified_by_id:
                fields.update(
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

        # memes_all.json은 그때그때의 델타가 아니라 전체 현황이다 — 이전 크롤링
        # 포맷(memes_nested.json 등)으로 들어와 있던, 지금 파일엔 없는 옛 행은 지운다.
        current_ids = {item["id"] for item in memes}
        stale = db.query(models.Meme).filter(models.Meme.id.notin_(current_ids)).all()
        removed = len(stale)
        for row in stale:
            db.delete(row)

        db.commit()
    finally:
        db.close()

    print(f"{ALL_PATH.name}: {len(memes)}건")
    print(f"완료 — 새로 추가 {inserted}건, 갱신 {updated}건, 이미지 없음 {missing_image}건, 삭제(옛 포맷 잔여) {removed}건")


if __name__ == "__main__":
    main()
