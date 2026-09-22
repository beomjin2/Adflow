"""광고 설정 — 종류와 컨셉만 고른다.

트렌드 조사는 제거됐다. 이미지 생성도 이 경로에는 없다 — 그림은 캐릭터 단계에서만
만들고, 광고 단계는 그 캐릭터로 무엇을 말할지(구성·대사)를 정하는 곳이다.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.routes.storyboard import reset_storyboard, set_trend_meme
from app.services.story_llm import cut_count
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
    """광고 설정을 확정한다.

    앞 단계가 안 끝났으면 무엇이 비었는지 한 문장으로 알려준다 — 그냥 막히면
    사장님은 어디가 문제인지 알 방법이 없다.

    body.trend_meme_id — 트렌드 화면에서 미리 골라 온 밈(있으면). 스토리보드에
    저장해 두면 대화가 스토리를 만들 때 자동으로 참고한다.

    🔴 **대화를 함부로 지우지 않는다.** 전에는 여기서 무조건 `reset_storyboard()`를
    불렀다. 그래서 대화를 한참 하다 "설정 바꾸기"로 잠깐 나갔다 돌아오기만 해도
    — 설정을 하나도 안 바꿨는데도 — 대화가 통째로 사라졌다.

    지우는 건 **컷 수가 바뀌었을 때뿐**이다. 4컷만화 ↔ 인스타 게시물(1컷)을 오가면
    지금 구성과 그려둔 그림이 개수부터 안 맞아서 살릴 수가 없다. 그 외에는
    (컨셉만 바꾸든, 아무것도 안 바꾸든) 대화를 그대로 두고 밈만 맞춘다.

    대화를 통째로 비우고 싶으면 대화창의 "처음부터"를 쓴다
    (`POST /api/storyboard/reset`) — 지우는 건 사장님이 정한다.
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

    # 앞 설정이 뭐였는지는 이미 덮어써져서 못 본다(프론트가 update 뒤에 apply를 부른다).
    # 대신 **지금 구성이 지금 광고 종류와 맞는지**를 본다 — 알고 싶은 게 그거다.
    sb = db.get(models.Storyboard, 1)
    plan = list((sb.plan if sb else None) or [])
    if plan and len(plan) != cut_count(ad.ad_type):
        reset_storyboard(db, trend_meme_id=body.trend_meme_id)
        return schemas.ApplyAdOut(
            ok=True,
            message=f"{ad.ad_type}는 컷 수가 달라서 대화를 새로 시작할게요.",
        )

    set_trend_meme(db, body.trend_meme_id)
    return schemas.ApplyAdOut(ok=True, message=f"{ad.ad_type} · {ad.ad_concept}로 만들어볼게요.")
