"""Pydantic 요청/응답 스키마. 채팅 메시지(kind별로 모양이 다름)는 프로토타입 단계라
엄격한 유니온 대신 dict로 느슨하게 다룬다 — 프론트 mock의 메시지 객체와 그대로 대응."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class ImageItem(BaseModel):
    label: str
    hue: int
    image: str | None = None


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
    messages: list[dict[str, Any]]
    pending: dict[str, Any]


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
    trend_applied: bool
    trend_pick: str


class AdUpdate(BaseModel):
    ad_type: str | None = None
    ad_concept: str | None = None


class ApplyAdOut(BaseModel):
    trend_popup: bool
    trend_yes_disabled: bool
    trend_hint: str


# ---------- trend ----------
class TrendBar(BaseModel):
    label: str
    value: int


class TrendDetail(BaseModel):
    name: str
    delta: str
    summary: str
    stats: list[dict[str, str]]
    links: list[dict[str, str]]


class TrendOut(BaseModel):
    bars: list[TrendBar]
    detail: list[TrendDetail]


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
