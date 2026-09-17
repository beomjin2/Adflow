"""Pydantic 요청/응답 스키마. 채팅 메시지는 kind마다 모양이 달라서 엄격한 유니온 대신
dict로 느슨하게 다룬다 — 프론트의 메시지 객체와 그대로 대응한다."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class ImageItem(BaseModel):
    label: str
    image: str | None = None
    # empty | generating | done | failed
    # 화면이 "그리는 중"과 "실패"를 구분해서 보여줘야 한다. 이게 없으면 사장님은
    # 빈 칸을 보고 그냥 고장난 걸로 읽는다.
    status: str = "empty"
    # 옛 데이터에 남아 있는 색상값. 새로 만들 때는 쓰지 않는다.
    hue: int = 0


# ---------- store ----------
class StoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    saved: bool
    category: str
    address: str
    hours: str
    open_time: str
    close_time: str
    closed_days: list[str]
    desc: str
    images: list[ImageItem]
    max_images: int


class StoreUpdate(BaseModel):
    category: str | None = None
    address: str | None = None
    open_time: str | None = None
    close_time: str | None = None
    closed_days: list[str] | None = None
    desc: str | None = None


# ---------- character ----------
class SheetRow(BaseModel):
    """시트 한 칸. 화면은 이 순서대로 그린다 — 순서가 곧 대화 가이드 순서다."""
    field: str
    label: str
    value: str
    auto: bool = False   # 사장님에게 묻지 않고 자동으로 채우는 칸(퍼스널 키워드)


class CharacterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    # ---- 시트 8칸 ----
    name: str
    age: str
    gender: str
    look: str
    outfit: str
    abilities: str
    keywords: list[str]
    desc: str

    # ---- 시트 진행 상태 ----
    sheet: list[SheetRow] = []        # 화면이 그대로 그리는 8줄
    sheet_complete: bool = False      # 전부 찼는가 — false면 후보 생성이 잠긴다
    missing: list[str] = []           # 아직 빈 칸의 라벨
    editing: str = ""                 # 대화가 지금 다루는 칸
    pending: dict[str, Any] = {}      # 승인 대기 중인 수정 제안

    confirmed: bool
    candidates: list[ImageItem]
    selected_index: int
    messages: list[dict[str, Any]]
    # 생성이 백그라운드로 돌기 때문에 화면이 폴링해야 한다. 아래 세 값이 그 근거다.
    generating: bool = False          # 하나라도 그리는 중인가 — true면 3초 뒤 다시 물어본다
    queue_depth: int = 0              # 내 앞에 몇 건이 기다리는가
    eta_seconds: int = 0              # 남은 것들이 끝나기까지 예상 시간


def character_out(char, queue_depth: int = 0) -> "CharacterOut":
    """DB 행 + 시트 진행 + 생성 진행을 합쳐 응답을 만든다."""
    from app.services import character_sheet as sheet
    from app.services.image_gen import eta_seconds as _eta

    drawing = sum(
        1
        for slot in list(char.candidates or [])
        if isinstance(slot, dict) and slot.get("status") == "generating"
    )
    out = CharacterOut.model_validate(char)
    out.sheet = [SheetRow(**row) for row in sheet.sheet_rows(char)]
    # 화면의 '그림 뽑기' 버튼이 이 값 하나로 잠기고 풀린다 — 키워드까지 포함한 판정이다.
    out.sheet_complete = sheet.ready_to_generate(char)
    out.missing = [
        sheet.KEYWORDS_LABEL if f == sheet.KEYWORDS_FIELD else sheet.LABELS[f]
        for f in sheet.missing_all(char)
    ]
    out.generating = drawing > 0
    out.queue_depth = queue_depth
    out.eta_seconds = _eta(drawing) if drawing else 0
    return out


class CharacterUpdate(BaseModel):
    """시트 직접 수정. 보낸 칸만 바뀐다."""
    name: str | None = None
    age: str | None = None
    gender: str | None = None
    look: str | None = None
    outfit: str | None = None
    abilities: str | None = None
    keywords: list[str] | None = None
    desc: str | None = None


class ChatIn(BaseModel):
    text: str


# ---------- ad ----------
class AdOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ad_type: str
    ad_concept: str


class AdUpdate(BaseModel):
    ad_type: str | None = None
    ad_concept: str | None = None


class ApplyAdOut(BaseModel):
    ok: bool
    message: str


# ---------- storyboard ----------
class StoryboardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    messages: list[dict[str, Any]]
    plan: list[dict[str, Any]]
    comic_cuts: list[dict[str, Any]]  # [{n, short, line, label, image, status}]
    prod_logged: bool
    pending: dict[str, Any]
    generating: bool = False          # 네컷 중 하나라도 그리는 중이면 3초 뒤 다시 물어본다
    queue_depth: int = 0
    eta_seconds: int = 0


def storyboard_out(sb, queue_depth: int = 0) -> "StoryboardOut":
    """DB 행 + 네컷 생성 진행 상태를 합쳐 응답을 만든다 (character_out과 같은 규칙)."""
    from app.services.image_gen import eta_seconds as _eta

    pending = sum(
        1 for cut in list(sb.comic_cuts or [])
        if isinstance(cut, dict) and cut.get("status") == "generating"
    )
    out = StoryboardOut.model_validate(sb)
    out.generating = pending > 0
    out.queue_depth = queue_depth
    out.eta_seconds = _eta(pending) if pending else 0
    return out


# ---------- meme ----------
class MemeCardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    source: str
    card: dict[str, Any]


class MemeCreate(BaseModel):
    title: str
    source: str = ""
    original: str


class ProposeIn(BaseModel):
    meme_id: int


# ---------- production ----------
class ProductionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str


class ProductionItemCreate(BaseModel):
    name: str


class ProductionRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    qty: str
    date: str
    time: str
    sold_out: str


class ProductionRecordCreate(BaseModel):
    name: str
    qty: str = ""
    date: str = ""
    time: str = ""
    sold_out: str = ""


class ProductionRecordPatch(BaseModel):
    name: str | None = None
    qty: str | None = None
    date: str | None = None
    time: str | None = None
    sold_out: str | None = None


# ---------- history ----------
class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    meta: str
    cuts: list[dict[str, Any]]


class HistoryCreate(BaseModel):
    title: str
    meta: str
    cuts: list[dict[str, Any]]


# ---------- trend ----------
class MemeOut(BaseModel):
    id: str
    source: str
    source_label: str
    name: str
    url: str
    image: str
    origin: str
    summary: str
    published: str
    views: str
    category: str
    situation: str = ""
    situation_score: float | None = None
    ad_safe: bool | None = None


class TrendSiteOut(BaseModel):
    source: str
    label: str
    count: int


class TrendOut(BaseModel):
    items: list[MemeOut]
    sites: list[TrendSiteOut]
