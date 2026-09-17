from sqlalchemy import JSON, Boolean, Column, Float, Integer, String

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


class MemeCard(Base):
    """밈 카드 — 밈 원문을 GPT가 한 번 읽어 정리한 것(정의·유행 이유·말 틀·시각 요소·업종·피할 것).

    사장님 데이터가 아니라 서비스가 갖고 있는 소재다. 그래서 히스토리·내보내기에는 섞이지
    않고, 스토리 제안(POST /api/storyboard/propose)의 입력으로만 쓴다. 비싼 단계(카드
    만들기)는 밈 하나당 한 번만 돌고 여기 저장된다.
    """
    __tablename__ = "meme_cards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    source = Column(String, default="")      # 사이트/원문 링크
    original = Column(String, default="")    # 카드를 만들 때 넣은 원문(요약이 아니라 본문)
    card = Column(JSON, default=dict)        # {definition, why, template, visual, industries, avoid, understanding}


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


class Meme(Base):
    """밈 레퍼런스 크롤링 데이터 — meam/*.json 원본을 그대로 옮겨 담는다 (import_memes.py).

    소스 3곳(gogumafarm, wepick_memepedia, maily_trendaword)이 컬럼 구성 자체가 서로 달라서,
    한 소스에만 있는 필드는 다른 소스 행에서는 빈 값으로 남는다. id는 각 소스 원본의
    id(maily는 post_id)를 그대로 쓴다.

    MemeCard(위)와는 다른 테이블이다 — MemeCard는 스토리 제안용으로 GPT가 요약한 카드,
    Meme은 트렌드 확인 화면이 그대로 훑어보는 원본 크롤링 데이터다.
    """
    __tablename__ = "memes"

    id = Column(String, primary_key=True)
    source = Column(String, default="")

    # 세 소스 공통
    url = Column(String, default="")
    meme_name = Column(String, default="")
    origin = Column(String, default="")
    image = Column(String, default="")

    # gogumafarm, wepick_memepedia 공통
    description = Column(String, default="")
    images = Column(JSON, default=list)
    tags = Column(JSON, default=list)
    published_date = Column(String, default="")

    # gogumafarm 전용
    from_article = Column(String, default="")

    # wepick_memepedia 전용
    category = Column(String, default="")
    author = Column(String, default="")
    view_count = Column(String, default="")
    videos = Column(JSON, default=list)
    article_title = Column(String, default="")
    collection_number = Column(String, default="")
    usage_source = Column(String, default="")

    # maily_trendaword 전용
    title = Column(String, default="")
    subtitle = Column(String, default="")
    published_at = Column(String, default="")
    thumbnail = Column(String, default="")
    image_from = Column(String, default="")
    origin_mode = Column(String, default="")
    usage = Column(String, default="")
    views = Column(String, default="")
    image_fix_note = Column(String, default="")

    # GPT 분류 결과 (meam/memes_classified.json, update_meme_situations.py) — 밈 필터가
    # 쓰는 상황 카테고리. situation_score는 그 카테고리로 분류될 때의 신뢰도.
    situation = Column(String, default="")
    situation_score = Column(Float, nullable=True)
    ad_safe = Column(Boolean, nullable=True)


class HistoryEntry(Base):
    """저장된(다운로드한) 광고 히스토리."""
    __tablename__ = "history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, default="")
    meta = Column(String, default="")
    cuts = Column(JSON, default=list)  # 저장 시점의 컷 목록
