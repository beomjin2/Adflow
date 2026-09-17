"""싱글턴 행만 만든다. 값은 하나도 채우지 않는다.

이 서비스는 데모가 아니라 실서비스다. 사장님이 처음 접속했을 때 DB에 들어 있어야 하는
값은 **없다** — 가게 정보도, 캐릭터도, 채팅 인사말도. 화면에 띄울 안내 문구는 화면의
몫이지 DB의 몫이 아니다. 여기에 문구를 넣으면 그 순간 그건 사장님이 만든 적 없는
데이터가 되어 히스토리·백업·내보내기에 그대로 섞인다.

라우터가 `db.get(..., 1)`로 찾기 때문에 행 자체는 존재해야 한다. 그래서 행만 만든다.
"""

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app import models


def ensure_rows(db: Session) -> None:
    """싱글턴 행이 없으면 빈 값으로 만든다. 이미 있으면 건드리지 않는다."""
    if not db.get(models.Store, 1):
        db.add(models.Store(
            id=1, saved=False, category="", address="", hours="",
            open_time="", close_time="", closed_days=[], desc="", images=[],
        ))

    if not db.get(models.Character, 1):
        # 시트 8칸 전부 빈 값으로. 예시 문구조차 넣지 않는다 — 화면이 안내할 몫이다.
        db.add(models.Character(
            id=1, name="", age="", gender="", look="", outfit="", abilities="",
            keywords=[], desc="", editing="", pending={},
            confirmed=False, candidates=[], selected_index=-1, messages=[],
        ))

    if not db.get(models.AdSettings, 1):
        db.add(models.AdSettings(id=1, ad_type="", ad_concept=""))

    if not db.get(models.Storyboard, 1):
        db.add(models.Storyboard(
            id=1, messages=[], plan=[], comic_cuts=[], prod_logged=False, pending={},
        ))

    # 밈 카드는 사장님 데이터가 아니라 서비스 소재라 위 원칙의 예외다. 팀이 원문에서 만든
    # 카드 4장(배경 담당 기록, 2026-09-16)을 비어 있을 때만 넣는다 — 히스토리·내보내기엔 안 섞인다.
    if db.query(models.MemeCard).count() == 0:
        seed_path = Path(__file__).with_name("meme_cards_seed.json")
        for row in json.loads(seed_path.read_text(encoding="utf-8")):
            db.add(models.MemeCard(**row))

    db.commit()


# 이전 이름 호환 — main.py가 부르던 이름.
seed_if_empty = ensure_rows
