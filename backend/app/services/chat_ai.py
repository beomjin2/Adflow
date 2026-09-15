"""채팅 응답 mock — 지금은 규칙 기반, 나중에 실제 LLM 연동으로 교체할 지점.
frontend/src/mock/aiResponses.js와 동일한 규칙을 그대로 포팅."""

import re
from datetime import datetime, timedelta

from app.services.image_gen import random_hue

VIEW_LABELS = ["정면", "좌측면", "우측면", "뒷면"]
VIEW_HINTS = {"정면": "front view", "좌측면": "left side view", "우측면": "right side view", "뒷면": "back view"}


def character_prompt(char, hint: str = "") -> str:
    base = (char.look or "").strip()
    if not base:
        base = ", ".join(p for p in [char.name, char.age, char.gender, char.hobby] if p) or "cute mascot character"
    pieces = [base, "mascot character illustration", "simple white background", "high quality", "anime style"]
    if hint:
        pieces.append(hint)
    return ", ".join(pieces)


def generate_candidates(count: int = 3) -> list[dict]:
    return [{"label": f"후보{i + 1}", "hue": random_hue()} for i in range(count)]


def generate_views() -> list[dict]:
    return [{"label": label, "hue": random_hue()} for label in VIEW_LABELS]


def iso_day(day_offset: int = 0) -> str:
    return (datetime.now() + timedelta(days=day_offset)).strftime("%Y-%m-%d")


def fmt_day(iso: str) -> str:
    parts = (iso or "").split("-")
    if len(parts) == 3:
        return f"{int(parts[1])}/{int(parts[2])}"
    return iso or ""


def now_hm() -> str:
    return datetime.now().strftime("%H:%M")


_ITEM_RE = re.compile(r"([가-힣a-zA-Z0-9]+(?:빵|크루아상|캄파뉴|케이크|쿠키|타르트))")
_QTY_RE = re.compile(r"(\d+)\s*개")
_DAY_RE = re.compile(r"(\d{1,2})\s*[/\-월.]\s*(\d{1,2})")
_TIME_RE = re.compile(r"(\d{1,2})\s*(?::|시)\s*(\d{1,2})?")
_SKIP_RE = re.compile(r"안\s?했|없어|없습니다|안했|건너|아니")


def item_from(text: str) -> str:
    m = _ITEM_RE.search(text or "")
    return m.group(1) if m else "신메뉴"


def qty_from(text: str) -> str:
    m = _QTY_RE.search(text or "")
    return f"{m.group(1)}개" if m else ""


def day_from(text: str) -> str:
    t = text or ""
    if "그저께" in t or "그제" in t:
        return iso_day(-2)
    if "어제" in t:
        return iso_day(-1)
    m = _DAY_RE.search(t)
    if m:
        now = datetime.now()
        return f"{now.year}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return iso_day(0)


def time_from(text: str) -> str:
    m = _TIME_RE.search(text or "")
    if not m:
        return now_hm()
    hour = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0
    return f"{hour:02d}:{minute:02d}"


def is_skip(text: str) -> bool:
    return bool(_SKIP_RE.search(text or ""))


def new_pid() -> str:
    import random
    import time
    return f"p{int(time.time() * 1000)}{random.randint(1000, 9999)}"
