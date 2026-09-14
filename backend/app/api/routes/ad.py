from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.routes.storyboard import reset_storyboard
from app.core.database import get_db

router = APIRouter(prefix="/api/ad", tags=["ad"])


def _get(db: Session) -> models.AdSettings:
    ad = db.get(models.AdSettings, 1)
    if not ad:
        raise HTTPException(404, "ad settings not seeded")
    return ad


@router.get("", response_model=schemas.AdOut)
def get_ad(db: Session = Depends(get_db)):
    return _get(db)


@router.put("", response_model=schemas.AdOut)
def update_ad(body: schemas.AdUpdate, db: Session = Depends(get_db)):
    ad = _get(db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(ad, field, value)
    db.commit()
    db.refresh(ad)
    return ad


@router.post("/apply", response_model=schemas.ApplyAdOut)
def apply_ad(db: Session = Depends(get_db)):
    ad = _get(db)
    menu = ad.ad_type == "메뉴판"
    hint = "메뉴판은 트렌드를 붙이기 어려워 '예'가 꺼져 있어요." if menu else "요즘 뜨는 밈을 얹으면 반응이 빨라요."
    return schemas.ApplyAdOut(trend_popup=True, trend_yes_disabled=menu, trend_hint=hint)


@router.post("/trend-yes", response_model=schemas.AdOut)
def trend_yes(db: Session = Depends(get_db)):
    ad = _get(db)
    ad.trend_applied = True
    db.commit()
    db.refresh(ad)
    reset_storyboard(db, with_trend=True, trend_pick=ad.trend_pick)
    return ad


@router.post("/trend-no", response_model=schemas.AdOut)
def trend_no(db: Session = Depends(get_db)):
    ad = _get(db)
    ad.trend_applied = False
    db.commit()
    db.refresh(ad)
    reset_storyboard(db, with_trend=False)
    return ad
