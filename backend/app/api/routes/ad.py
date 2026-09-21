"""광고 설정 — 종류와 컨셉만 고른다.

트렌드 조사는 제거됐다. 이미지 생성도 이 경로에는 없다 — 그림은 캐릭터 단계에서만
만들고, 광고 단계는 그 캐릭터로 무엇을 말할지(구성·대사)를 정하는 곳이다.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.routes.storyboard import reset_storyboard
from app.core.database import get_db

router = APIRouter(prefix="/api/ad", tags=["ad"])

AD_TYPES = ["인스타 게시물", "4컷만화"]


def _get(db: Session) -> models.AdSettings:
    ad = db.get(models.AdSettings, 1)
    if not ad:
        raise HTTPException(404, "ad settings row missing")
    return ad


@router.get("", response_model=schemas.AdOut)
def get_ad(db: Session = Depends(get_db)):
    return _get(db)


@router.put("", response_model=schemas.AdOut)
def update_ad(body: schemas.AdUpdate, db: Session = Depends(get_db)):
    ad = _get(db)
    values = body.model_dump(exclude_unset=True)
    if values.get("ad_type") and values["ad_type"] not in AD_TYPES:
        raise HTTPException(422, f"광고 종류는 {', '.join(AD_TYPES)} 중에서 골라주세요")
    for field, value in values.items():
        setattr(ad, field, value)
    db.commit()
    db.refresh(ad)
    return ad


@router.post("/apply", response_model=schemas.ApplyAdOut)
def apply_ad(body: schemas.ApplyAdIn = schemas.ApplyAdIn(), db: Session = Depends(get_db)):
    """광고 설정을 확정하고 스토리보드 대화를 처음부터 시작한다.

    앞 단계가 안 끝났으면 무엇이 비었는지 한 문장으로 알려준다 — 그냥 막히면
    사장님은 어디가 문제인지 알 방법이 없다.

    body.trend_meme_id — 트렌드 화면에서 미리 골라 온 밈(있으면). 스토리보드에
    저장해 두면 대화가 스토리를 만들 때 자동으로 참고한다.
    """
    ad = _get(db)

    missing = []
    store = db.get(models.Store, 1)
    if not store or not store.saved:
        missing.append("가게 정보 저장")
    char = db.get(models.Character, 1)
    if not char or not char.confirmed:
        missing.append("캐릭터 확정")
    if not ad.ad_type:
        missing.append("광고 종류 선택")
    if not ad.ad_concept:
        missing.append("광고 컨셉 선택")
    if missing:
        raise HTTPException(400, f"{' · '.join(missing)}이(가) 먼저 필요해요")

    reset_storyboard(db, trend_meme_id=body.trend_meme_id)
    return schemas.ApplyAdOut(ok=True, message=f"{ad.ad_type} · {ad.ad_concept}로 만들어볼게요.")
