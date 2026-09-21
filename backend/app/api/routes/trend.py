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
        period_end=m.period_end or "",
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

    # 수집 시점이 섞여 있으면(사이트별로 따로 돌린 경우) 가장 최근 것을 기준으로 삼는다.
    collected_at = max((m.collected_at or "" for m in rows), default="")
    # collected_at 은 import_memes.py 가 채운다. 배포 뒤 그걸 안 돌리면 전부 빈 값이라
    # 화면이 기준일을 못 구해 "유행 중" 배지가 에러 없이 통째로 사라진다(실제로 한 번 겪었다).
    # 그럴 때만 밈들의 마지막 신호일(period_end) 중 가장 늦은 날로 대신한다.
    # 정상 경로로 쓰지 않는 이유: 최근에 뜬 밈이 하나도 없는 달엔 이 값이 과거로 밀린다.
    # 비상용이라 import 를 다시 돌리면 자동으로 정상 값으로 돌아간다.
    if not collected_at:
        collected_at = max((m.period_end or "" for m in rows), default="")

    return schemas.TrendOut(items=items, sites=sites, collected_at=collected_at)


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
