import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.services.meme_recommend import recommend_meme

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trend", tags=["trend"])


def _sort_key(m: models.Meme) -> str:
    """정렬 기준 날짜는 화면이 실제로 보여주는 날짜(period_start > peak_date > published_date)와
    맞춘다. 표기가 소스·필드마다 달라서("2026-08-26" vs "2026. 08. 26") 문자열 그대로
    비교하면 섞였을 때 순서가 어긋난다. 숫자만 남겨 YYYYMMDD로 맞춘다.
    셋 다 없으면 빈 문자열이 되어 맨 뒤로 간다."""
    date = m.period_start or m.peak_date or m.published_date or ""
    return "".join(ch for ch in date if ch.isdigit())


def _to_meme_out(m: models.Meme) -> schemas.MemeOut:
    return schemas.MemeOut(
        id=m.id,
        source=m.source,
        source_label=m.source_label or m.source,
        name=m.meme_name,
        url=m.url,
        image=m.image or "",
        origin=m.origin,
        summary=m.usage_example or "",
        published=m.published_date or "",
        period_start=m.period_start or "",
        peak_date=m.peak_date or "",
        views=m.views,
        situation=m.situation or "",
        situation_score=m.situation_score,
        ad_safe=m.ad_safe,
    )


@router.get("", response_model=schemas.TrendOut)
def list_trend(db: Session = Depends(get_db)):
    rows = db.query(models.Meme).all()
    rows.sort(key=_sort_key, reverse=True)

    items = [_to_meme_out(m) for m in rows]
    counts: dict[str, int] = {}
    labels: dict[str, str] = {}
    for m in rows:
        counts[m.source] = counts.get(m.source, 0) + 1
        labels[m.source] = m.source_label or m.source

    sites = [
        schemas.TrendSiteOut(source=src, label=labels[src], count=n)
        for src, n in counts.items()
    ]
    sites.sort(key=lambda s: s.label)

    return schemas.TrendOut(items=items, sites=sites)


@router.post("/recommend", response_model=schemas.TrendRecommendOut)
def recommend(body: schemas.TrendRecommendIn, db: Session = Depends(get_db)):
    """활용 상황 하나를 골라 그 안에서 밈 하나를 GPT로 추천받는다.

    캐릭터가 아직 확정 안 됐어도 부른다 — 트렌드 확인 화면은 캐릭터 없이도 들어올 수
    있는 화면이라, 캐릭터 정보는 있으면 참고하고 없으면 그냥 빼고 추천한다.
    """
    candidates = db.query(models.Meme).filter(models.Meme.situation == body.situation).all()
    if not candidates:
        raise HTTPException(404, "이 활용 상황에 해당하는 밈이 없어요")

    char = db.get(models.Character, 1)
    character_desc = ""
    if char and char.confirmed:
        parts = [char.name, char.look, char.outfit, char.abilities, ", ".join(char.keywords or []), char.desc]
        character_desc = " / ".join(p for p in parts if p)

    try:
        pick = recommend_meme(
            situation=body.situation,
            note=body.note.strip(),
            character_desc=character_desc,
            candidates=[
                {"id": m.id, "name": m.meme_name, "origin": m.origin, "usage_example": m.usage_example}
                for m in candidates
            ],
        )
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception:
        logger.exception("밈 추천 실패")
        raise HTTPException(502, "추천을 만들지 못했어요. 잠시 뒤 다시 시도해 주세요")

    meme = next(m for m in candidates if m.id == pick["meme_id"])
    return schemas.TrendRecommendOut(meme=_to_meme_out(meme), reason=pick["reason"])
