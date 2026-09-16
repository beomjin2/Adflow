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
class CharacterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    age: str
    gender: str
    hobby: str
    look: str
    confirmed: bool
    candidates: list[ImageItem]
    selected_index: int
    views: list[ImageItem]
    messages: list[dict[str, Any]]
    # 생성이 백그라운드로 돌기 때문에 화면이 폴링해야 한다. 아래 세 값이 그 근거다.
    generating: bool = False          # 하나라도 그리는 중인가 — true면 3초 뒤 다시 물어본다
    queue_depth: int = 0              # 내 앞에 몇 건이 기다리는가
    eta_seconds: int = 0              # 남은 것들이 끝나기까지 예상 시간


def character_out(char, queue_depth: int = 0) -> "CharacterOut":
    """DB 행 + 생성 진행 상태를 합쳐 응답을 만든다."""
    from app.services.image_gen import eta_seconds as _eta

    pending = sum(
        1
        for slot in list(char.candidates or []) + list(char.views or [])
        if isinstance(slot, dict) and slot.get("status") == "generating"
    )
    out = CharacterOut.model_validate(char)
    out.generating = pending > 0
    out.queue_depth = queue_depth
    out.eta_seconds = _eta(pending) if pending else 0
    return out


class CharacterUpdate(BaseModel):
    name: str | None = None
    age: str | None = None
    gender: str | None = None
    hobby: str | None = None
    look: str | None = None


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
    comic_cuts: list[dict[str, Any]]
    prod_logged: bool
    pending: dict[str, Any]


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
