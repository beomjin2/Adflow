import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.services.meme_recommend import recommend as recommend_meme

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

    return schemas.TrendOut(items=items, sites=sites, collected_at=collected_at)


@router.post("/recommend", response_model=schemas.TrendRecommendOut)
async def recommend(body: schemas.TrendRecommendIn, db: Session = Depends(get_db)):
    """GPT 호출 한 번으로, 활용 상황(situation)을 먼저 고르고 그 상황 안에서 밈을 하나
    고른다(meme_recommend.py 참고) — 호출을 나눴더니 매번 왕복 두 번이라 느려서, 한 번의
    응답 안에 두 단계를 다 넣었다.

    이 라우트만 async def다 — GPT 호출을 비동기(AsyncOpenAI)로 바꿔서, 응답을 기다리는
    동안 서버가 다른 요청도 같이 처리할 수 있게 했다. DB 조회는 그대로 동기(SQLAlchemy
    Session)라 이벤트 루프를 잠깐씩 쓰지만, 로컬 쿼리라 오래 걸리지 않아 문제되지 않는다.

    가게 정보·캐릭터 둘 다 아직 확정 안 됐어도 부른다 — 트렌드 확인 화면은 그 전에도
    들어올 수 있는 화면이라, 있으면 참고하고 없으면 그냥 빼고 추천한다.
    """
    # "미분류"는 크롤링 파이프라인이 분류 못 했다는 표시일 뿐 진짜 활용 상황이 아니다.
    # 후보로 주면 맥락이 약할 때(오늘 알릴 내용을 안 적었을 때 등) GPT가 "애매하면 여기"
    # 식으로 자꾸 이쪽을 고르는 경향이 있었다 — 아예 후보에서 뺀다.
    all_memes = [m for m in db.query(models.Meme).all() if m.situation and m.situation != "미분류"]
    if not all_memes:
        raise HTTPException(404, "추천할 밈이 없어요")

    store = db.get(models.Store, 1)
    store_desc = ""
    if store and store.saved:
        parts = [store.category, store.address, store.hours, store.desc]
        store_desc = " / ".join(p for p in parts if p)

    char = db.get(models.Character, 1)
    character_desc = ""
    if char and char.confirmed:
        parts = [char.name, char.look, char.outfit, char.abilities, ", ".join(char.keywords or []), char.desc]
        character_desc = " / ".join(p for p in parts if p)

    try:
        result = await recommend_meme(
            body.note.strip(), character_desc, store_desc,
            candidates=[
                {"id": m.id, "name": m.meme_name, "situation": m.situation,
                 "origin": m.origin, "usage_example": m.usage_example}
                for m in all_memes
            ],
        )
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception:
        logger.exception("밈 추천 실패")
        raise HTTPException(502, "추천을 만들지 못했어요. 잠시 뒤 다시 시도해 주세요")

    by_id = {m.id: m for m in all_memes}
    return schemas.TrendRecommendOut(
        situation=result["situation"],
        picks=[
            schemas.TrendRecommendPick(meme=_to_meme_out(by_id[p["meme_id"]]), reason=p["reason"])
            for p in result["picks"]
        ],
    )
