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

[누적 방식] 크롤링할 때마다 DB를 갈아엎지 않고 쌓는다.
- 같은 밈인지는 id(글 번호 기반이라 크롤링마다 바뀜)가 아니라 띄어쓰기를 뺀 밈 이름으로
  판단한다(merged_from에 남은 다른 사이트 표기도 같이 비교).
- 새 밈: 전부 저장한다.
- 이미 있는 밈: id와 사이트 내용(이름·유래·활용 예시·등록일·이미지·링크 등)은 처음 수집한
  것을 그대로 둔다. 밈 내용은 한 번 쓰이면 거의 안 바뀌고, 다시 덮어쓰면 파싱 실패로 멀쩡한
  내용이 망가질 위험만 있어서다. 비어 있는 칸만 채운다.
  바뀌는 정보(조회수·순위·수집일·유행 날짜)와 새로 발견된 출처(merged_from)만 반영한다.
- 이번 파일에 없는 밈은 지우지 않는다(지난달 밈도 트렌드 화면에 남는다).
- 화면의 "최근 수집"은 collected_at 전체 중 최댓값이다.

유행 날짜는 원래 사이트 크롤링과 별개로, DB에 있는 밈 전체를 대상으로 네이버 검색량을
다시 재서 갱신해야 한다(사이트 목록에서 빠진 밈도 여전히 유행 중일 수 있으므로). 그 단계가
따로 생기기 전까지는 여기서 파일에 담긴 측정값으로만 갱신한다.
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


def _meme_key(name: str) -> str:
    """같은 밈 판정용 키. "연락 없네 잘 살아"와 "연락없네잘살아"를 같은 밈으로 본다."""
    return re.sub(r"\s+", "", name or "").lower()


# 처음 수집한 값을 유지하는 사이트 내용 칸 — 비어 있을 때만 채운다.
_KEEP_FIELDS = (
    "source", "source_label", "url", "meme_name", "origin", "usage_example",
    "published_date", "image", "search_terms",
)
_TREND_FIELDS = ("period_start", "period_end", "peak_date", "trend_method", "pre_existing", "blog_total")


def _update_existing(row, fields: dict, item: dict) -> None:
    """이미 DB에 있는 밈을 갱신한다. id와 사이트 내용은 건드리지 않는다."""
    for key in _KEEP_FIELDS:
        if not getattr(row, key) and fields.get(key):
            setattr(row, key, fields[key])

    # 매번 달라지는 정보
    row.views = fields["views"]
    row.rank_in_source = fields["rank_in_source"]
    row.collected_at = fields["collected_at"]
    if fields.get("trend_method"):  # 측정값이 있을 때만 (없으면 예전 측정값 유지)
        for key in _TREND_FIELDS:
            setattr(row, key, fields[key])
    for key in ("situation", "situation_score", "ad_safe"):
        if key in fields:
            setattr(row, key, fields[key])

    # 새로 발견된 출처는 merged_from / links에 덧붙인다.
    merged = list(row.merged_from or [])
    seen = {row.url} | {m.get("url") for m in merged}
    candidates = [dict(id=item["id"], source=item.get("source") or "", source_label=item.get("source_label") or "",
                       name=item.get("name") or "", url=item.get("url") or "")]
    candidates += item.get("merged_from") or []
    for c in candidates:
        if c.get("url") and c["url"] not in seen:
            merged.append(c)
            seen.add(c["url"])
    row.merged_from = merged

    links = list(row.links or [])
    hrefs = {l.get("href") for l in links}
    for l in fields.get("links") or []:
        if l.get("href") and l["href"] not in hrefs:
            links.append(l)
            hrefs.add(l["href"])
    row.links = links


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
    # "2026-09-17T17:54:15" -> "2026-09-17". 이 파일을 만든 시점이 곧 수집 기준일이다.
    collected_at = ((data.get("_meta") or {}).get("generated_at") or "")[:10]

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
        # 이미 DB에 있는 밈을 이름 키로 색인한다. merged_from에 남은 다른 사이트 표기도
        # 같이 넣어 둬서, 다음 크롤링에서 그 표기로 들어와도 같은 밈으로 잡히게 한다.
        existing_by_key: dict[str, models.Meme] = {}
        for row in db.query(models.Meme).all():
            names = [row.meme_name] + [m.get("name") or "" for m in (row.merged_from or [])]
            for n in names:
                k = _meme_key(n)
                if k:
                    existing_by_key.setdefault(k, row)
        before_ids = {r.id for r in existing_by_key.values()}
        touched_ids: set[str] = set()

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
                collected_at=collected_at,
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
            names = [item.get("name") or ""] + [m.get("name") or "" for m in (item.get("merged_from") or [])]
            keys = [k for k in (_meme_key(n) for n in names) if k]
            row = next((existing_by_key[k] for k in keys if k in existing_by_key), None)
            if row is None:
                row = db.get(models.Meme, fields["id"])  # 이름은 달라도 id가 겹치는 경우 대비
            if row is None:
                row = models.Meme(**fields)
                db.add(row)
                inserted += 1
            else:
                _update_existing(row, fields, item)
                updated += 1
            touched_ids.add(row.id)
            for k in keys:
                existing_by_key[k] = row

        db.commit()
        kept = len(before_ids - touched_ids)  # 이번 파일엔 없지만 지우지 않고 남겨 둔 밈
    finally:
        db.close()

    print(f"{ALL_PATH.name}: {len(memes)}건")
    print(f"완료 — 새로 추가 {inserted}건, 갱신 {updated}건, 이번엔 없어서 그대로 둔 밈 {kept}건, 이미지 없음 {missing_image}건")


if __name__ == "__main__":
    main()
