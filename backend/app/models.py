from sqlalchemy import JSON, Boolean, Column, Integer, String

from app.core.config import STORE_MAX_IMAGES
from app.core.database import Base


class Store(Base):
    """가게 정보 — 싱글턴 (id=1 고정, 지금은 매장 하나만 다룬다).

    기본값은 전부 빈 값이다. 사장님이 처음 들어왔을 때 남의 가게 업종·영업시간이
    이미 채워져 있으면 그건 서비스가 아니라 데모다.
    """
    __tablename__ = "store"

    id = Column(Integer, primary_key=True, default=1)
    saved = Column(Boolean, default=False)
    category = Column(String, default="")
    address = Column(String, default="")
    hours = Column(String, default="")  # open_time/close_time/closed_days로 자동 계산되는 표시용 문자열
    open_time = Column(String, default="")
    close_time = Column(String, default="")
    closed_days = Column(JSON, default=list)  # ["월", "화", ...]
    desc = Column(String, default="")
    images = Column(JSON, default=list)  # [{label, image}] — image: 사장님이 올린 파일 URL

    @property
    def max_images(self) -> int:
        return STORE_MAX_IMAGES


class Character(Base):
    """마스코트 캐릭터 시트 — 싱글턴 (id=1).

    시트 8칸이 전부 채워져야 후보 생성이 열린다(services/character_sheet.py).
    그중 퍼스널 키워드는 사장님에게 묻지 않고 마지막에 자동으로 뽑아 제안한다.
    """
    __tablename__ = "character"

    id = Column(Integer, primary_key=True, default=1)

    # ---- 시트 8칸 ----
    name = Column(String, default="")        # 이름
    age = Column(String, default="")         # 나이
    gender = Column(String, default="")      # 성별
    look = Column(String, default="")        # 외형   ← 이미지 태깅에 쓰임
    outfit = Column(String, default="")      # 아웃핏 ← 이미지 태깅에 쓰임
    abilities = Column(String, default="")   # 능력
    keywords = Column(JSON, default=list)    # 퍼스널 키워드 ["느긋한", ...] — 자동 제안
    desc = Column(String, default="")        # 설명

    # 대화가 지금 어느 칸을 다루는 중인가. 가이드 순서를 이 값으로 걸어 둔다.
    editing = Column(String, default="")
    # {pid: {kind, field, diffs, payload, status}} — 시트 완성 후 수정은 전/후를 보여주고 승인받는다
    pending = Column(JSON, default=dict)

    confirmed = Column(Boolean, default=False)
    candidates = Column(JSON, default=list)  # [{label, image, status}]
    selected_index = Column(Integer, default=-1)
    messages = Column(JSON, default=list)  # [{role, kind, ...}] 채팅 히스토리

    # 쓰지 않는다. 예전 DB에 남아 있어 컬럼만 유지한다.
    # hobby: '취미'는 시트에서 '능력'과 '설명'으로 갈라졌다.
    # views: 4방향 뽑기는 걷어냈다.
    hobby = Column(String, default="")
    views = Column(JSON, default=list)


class AdSettings(Base):
    """광고 종류/컨셉 — 싱글턴 (id=1). 둘 다 사장님이 직접 고른다."""
    __tablename__ = "ad_settings"

    id = Column(Integer, primary_key=True, default=1)
    ad_type = Column(String, default="")
    ad_concept = Column(String, default="")


class Storyboard(Base):
    """스토리보드 채팅/플랜/네컷만화 진행 상태 — 싱글턴 (id=1)."""
    __tablename__ = "storyboard"

    id = Column(Integer, primary_key=True, default=1)
    messages = Column(JSON, default=list)  # [{role, kind, ...}]
    plan = Column(JSON, default=list)      # [{n, line, short}]
    comic_cuts = Column(JSON, default=list)  # [{n, short, line}]
    prod_logged = Column(Boolean, default=False)
    pending = Column(JSON, default=dict)   # {pid: {which, kind, diffs, payload, status}}


class ProductionItem(Base):
    """생산 기록에 쓸 품목 목록."""
    __tablename__ = "production_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)


class ProductionRecord(Base):
    """생산 기록 (품목/수량/생산일시/매진시각)."""
    __tablename__ = "production_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    qty = Column(String, default="")
    date = Column(String, default="")
    time = Column(String, default="")
    sold_out = Column(String, default="")


class HistoryEntry(Base):
    """저장된(다운로드한) 광고 히스토리."""
    __tablename__ = "history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, default="")
    meta = Column(String, default="")
    cuts = Column(JSON, default=list)  # 저장 시점의 컷 목록
