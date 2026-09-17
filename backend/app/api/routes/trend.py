from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db

router = APIRouter(prefix="/api/trend", tags=["trend"])

SOURCE_LABELS = {
    "gogumafarm": "고구마팜",
    "wepick_memepedia": "위픽레터",
    "maily_trendaword": "Trend A Word",
}


def _sort_key(m: models.Meme) -> str:
    """published_date/published_at 표기가 소스마다 달라서("2026. 08. 26" vs "2026.09.10")
    문자열 그대로 비교하면 섞였을 때 순서가 어긋난다. 숫자만 남겨 YYYYMMDD로 맞춘다.
    값이 없으면(위픽레터) 빈 문자열이 되어 맨 뒤로 간다."""
    raw = m.published_date or m.published_at or ""
    return "".join(ch for ch in raw if ch.isdigit())


@router.get("", response_model=schemas.TrendOut)
def list_trend(db: Session = Depends(get_db)):
    rows = db.query(models.Meme).all()
    rows.sort(key=_sort_key, reverse=True)

    items = []
    counts: dict[str, int] = {}
    for m in rows:
        counts[m.source] = counts.get(m.source, 0) + 1
        items.append(schemas.MemeOut(
            id=m.id,
            source=m.source,
            source_label=SOURCE_LABELS.get(m.source, m.source),
            name=m.meme_name,
            url=m.url,
            image=m.image or m.thumbnail or "",
            origin=m.origin,
            summary=m.description or m.usage or "",
            published=m.published_date or m.published_at or "",
            views=m.views or m.view_count or "",
            category=m.category,
            situation=m.situation or "",
            situation_score=m.situation_score,
            ad_safe=m.ad_safe,
        ))

    sites = [
        schemas.TrendSiteOut(source=src, label=SOURCE_LABELS.get(src, src), count=n)
        for src, n in counts.items()
    ]
    sites.sort(key=lambda s: s.label)

    return schemas.TrendOut(items=items, sites=sites)
