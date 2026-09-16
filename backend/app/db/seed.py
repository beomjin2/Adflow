"""데모 시드 데이터 — frontend/src/state/useAdMakerState.js의 SEEDED 초기값과 동일."""

from sqlalchemy.orm import Session

from app import models
from app.services.chat_ai import iso_day


def seed_if_empty(db: Session) -> None:
    if not db.get(models.Store, 1):
        db.add(models.Store(
            id=1, saved=True, category="베이커리",
            address="서울 마포구 연남로 21",
            open_time="08:00", close_time="20:00", closed_days=["월"],
            hours="08:00 – 20:00, 월 휴무",
            desc="매일 새벽 반죽해 오븐에서 바로 꺼내는 동네 빵집. 소금빵과 통밀 캄파뉴가 간판이에요.",
            images=[{"label": "소금빵", "hue": 38}, {"label": "오늘 구운 빵 진열대", "hue": 26}],
        ))

    if not db.get(models.Character, 1):
        db.add(models.Character(
            id=1,
            messages=[{"role": "ai", "kind": "text", "text": "어떤 마스코트를 원하세요? 가게 분위기나 느낌을 편하게 말해주세요."}],
        ))

    if not db.get(models.AdSettings, 1):
        db.add(models.AdSettings(id=1, trend_pick="눈이 번쩍 챌린지"))

    if not db.get(models.Storyboard, 1):
        db.add(models.Storyboard(
            id=1,
            messages=[{"role": "ai", "kind": "text", "text": "어떤 이야기로 광고를 만들까요? 알리고 싶은 걸 말해주세요."}],
        ))

    if db.query(models.ProductionItem).count() == 0:
        for name in ["소금빵", "버터 크루아상", "통밀 캄파뉴"]:
            db.add(models.ProductionItem(name=name))

    if db.query(models.ProductionRecord).count() == 0:
        db.add_all([
            models.ProductionRecord(name="소금빵", qty="60개", date=iso_day(0), time="07:40", sold_out=""),
            models.ProductionRecord(name="버터 크루아상", qty="40개", date=iso_day(-1), time="13:20", sold_out=""),
            models.ProductionRecord(name="통밀 캄파뉴", qty="12개", date=iso_day(-1), time="06:50", sold_out="16:10"),
        ])

    db.commit()
