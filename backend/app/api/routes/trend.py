from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.routes.storyboard import reset_storyboard
from app.core.database import get_db
from app.services.trend_data import TREND_DETAIL, trend_bars

router = APIRouter(prefix="/api/trend", tags=["trend"])


@router.get("", response_model=schemas.TrendOut)
def get_trend():
    return schemas.TrendOut(bars=trend_bars(), detail=TREND_DETAIL)


@router.post("/use/{name}", response_model=schemas.AdOut)
def use_trend(name: str, db: Session = Depends(get_db)):
    char = db.get(models.Character, 1)
    if not char or not char.confirmed:
        raise HTTPException(400, "캐릭터를 먼저 확정해주세요")
    ad = db.get(models.AdSettings, 1)
    if not ad:
        raise HTTPException(404, "ad settings not seeded")
    ad.trend_pick = name
    ad.trend_applied = True
    db.commit()
    db.refresh(ad)
    reset_storyboard(db, with_trend=True, trend_pick=name)
    return ad
