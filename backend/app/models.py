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
    # 쓰지 않는다. 예전엔 대화 첫 마디를 생산 기록으로 받았는지 표시했는데, 그 기능을
    # 없애면서(생산 기록은 "내 정보 > 생산 기록" 탭에서만 남긴다) 더는 안 읽는다.
    # 컬럼은 지우지 않는다 — 예전 DB에 남아 있고, 지우려면 별도 마이그레이션이 필요하다.
    prod_logged = Column(Boolean, default=False)
    pending = Column(JSON, default=dict)   # {pid: {which, kind, diffs, payload, status}}
    # 트렌드 확인 화면에서 미리 골라 온 밈(Meme.id). 광고 설정을 확정할 때(POST /api/ad/apply)
    # 같이 저장되고, 대화(story_llm.plan_from_text)가 스토리를 만들 때 참고한다.
    # 안 골랐으면 빈 문자열 — 그때는 밈 얘기 자체를 안 한다(GPT가 스스로 고르지 않는다).
    trend_meme_id = Column(String, default="")
    # 위 밈의 이름 — 화면에 바로 보여주려고 같이 저장해 둔다(그때마다 memes 테이블을
    # 다시 조회하지 않는다). trend_meme_id를 정할 때 한 번만 같이 채운다.
    trend_meme_name = Column(String, default="")
    # 인스타에 올릴 캡션 — 컷 대사(plan[].line)는 말풍선용이라 40자 제한이 있어 그대로
    # 이어붙이면 SNS 톤이 안 산다. plan을 승인할 때마다(POST /confirm) GPT가 이모지·
    # 줄바꿈·해시태그가 있는 캡션을 따로 새로 쓴다(story_llm.generate_caption). 실패하면
    # 빈 문자열로 남고, 그때는 화면이 옛 방식(컷 이어붙이기)으로 대신 보여준다.
    caption = Column(String, default="")


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
    """밈 레퍼런스 크롤링 데이터 — crawling/memes_all.json을 그대로 옮겨 담는다
    (import_memes.py). 그 파일이 사이트별 크롤링 결과에서 같은 내용의 밈을 이미
    걸러낸(중복 제거) 산출물이라, 여기 컬럼도 소스별로 갈라지지 않고 하나로 통일돼 있다.
    같은 밈이 사이트마다 다르게 표현돼도 merged_from에 나머지 출처가 그대로 남는다.

    이 원본(유래 origin·활용예시 usage_example)을 트렌드 추천(meme_recommend.py)과
    스토리 생성(story_llm.py)이 그대로 GPT에 넘긴다 — 따로 요약·정리해 둔 카드는 없다.
    """
    __tablename__ = "memes"

    id = Column(String, primary_key=True)
    source = Column(String, default="")
    source_label = Column(String, default="")
    url = Column(String, default="")
    meme_name = Column(String, default="")
    origin = Column(String, default="")
    usage_example = Column(String, default="")
    published_date = Column(String, default="")
    views = Column(Integer, nullable=True)
    rank_in_source = Column(Integer, nullable=True)
    # crawling/images/의 로컬 사본 경로("/api/meme-images/xxx.jpg").
    image = Column(String, default="")

    # 네이버 검색량 기반 트렌드 구간 (crawling/memes_all.json의 trend). method가
    # "none"이면 스파이크를 못 찾은 경우라 나머지 필드가 비어 있다 — 화면은 이때
    # published_date로 대신 보여준다(트렌드 확인 화면 날짜 표시 우선순위: period_start > published_date).
    period_start = Column(String, default="")
    period_end = Column(String, default="")
    peak_date = Column(String, default="")
    trend_method = Column(String, default="")
    pre_existing = Column(Boolean, nullable=True)
    blog_total = Column(Integer, nullable=True)

    # 이 행을 어느 시점의 수집 결과로 채웠는지(crawling/memes_all.json 의 _meta.generated_at).
    # "유행 중" 판정의 기준일이다 — 실행 시각(오늘)을 쓰면 크롤링이 몇 주에 한 번 도는 동안
    # 살아 있던 밈이 전부 종료로 바뀐다(밈이 끝난 게 아니라 우리가 안 훑은 건데도).
    collected_at = Column(String, default="")

    search_terms = Column(JSON, default=list)
    links = Column(JSON, default=list)
    merged_from = Column(JSON, default=list)

    # GPT 분류 결과 (crawling/memes_classified.json) — 밈 필터가 쓰는 상황 카테고리.
    # situation_score는 그 카테고리로 분류될 때의 신뢰도.
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
    caption = Column(String, default="")  # 저장 시점의 SNS 캡션(있으면)
