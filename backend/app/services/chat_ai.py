"""대화 입력에서 값을 뽑아내는 규칙(생산 품목·수량·날짜·시각)과 캐릭터 프롬프트 조립.

채팅 응답은 아직 규칙 기반이다 — LLM을 붙이는 자리는 storyboard 쪽이고, 여기는
사장님이 한국어로 쓴 문장에서 숫자·품목·시각을 읽어내는 파서다.
"""

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# 서버는 UTC로 돈다. 그대로 쓰면 새벽 5시에 구운 빵이 '어제' 생산으로 기록된다 —
# 새벽에 굽는 가게가 많으니 여기서 한국 시간으로 고정한다.
KST = ZoneInfo("Asia/Seoul")


def _now() -> datetime:
    return datetime.now(timezone.utc).astimezone(KST)

VIEW_LABELS = ["정면", "좌측면", "우측면", "뒷면"]
VIEW_HINTS = {"정면": "front view", "좌측면": "left side view", "우측면": "right side view", "뒷면": "back view"}

# '연습용' 워크플로우가 이 태그 조합에 맞춰 조정돼 있다. 사장님이 쓴 설명 앞에 붙여
# 화풍을 고정한다 — 이걸 빼면 같은 모델에서도 그림 톤이 매번 달라진다.
STYLE_TAGS = "masterpiece, best quality, score_7, safe, solo, (chibi:1.3), full body, simple background"


def character_prompt(char, hint: str = "") -> str:
    """사장님이 입력한 캐릭터 설명을 '연습용' 워크플로우의 프롬프트로 조립한다."""
    described = (char.look or "").strip()
    if not described:
        described = ", ".join(p for p in [char.name, char.age, char.gender, char.hobby] if p)

    pieces = [STYLE_TAGS]
    if described:
        pieces.append(described)
    else:
        pieces.append("cute animal mascot character")
    if hint:
        pieces.append(hint)
    return ", ".join(pieces)


def pending_candidates(count: int = 3) -> list[dict]:
    """생성 대기 칸 count개. 이미지는 백그라운드 워커가 나중에 채운다."""
    return [
        {"label": f"후보{i + 1}", "image": None, "status": "generating"}
        for i in range(count)
    ]


def pending_views() -> list[dict]:
    """4방향 생성 대기 칸."""
    return [
        {"label": label, "image": None, "status": "generating"}
        for label in VIEW_LABELS
    ]


def iso_day(day_offset: int = 0) -> str:
    return (_now() + timedelta(days=day_offset)).strftime("%Y-%m-%d")


def fmt_day(iso: str) -> str:
    parts = (iso or "").split("-")
    if len(parts) == 3:
        return f"{int(parts[1])}/{int(parts[2])}"
    return iso or ""


def now_hm() -> str:
    return _now().strftime("%H:%M")


# 품목은 업종마다 다르다 — 빵집이든 반찬가게든 꽃집이든 같은 규칙으로 읽어야 한다.
# 그래서 품목 사전을 두지 않고, 문장에서 수량·날짜·시각·동사를 걷어낸 나머지를 품목으로 본다.
_UNIT = r"개|봉지|봉|판|장|잔|병|팩|박스|세트|인분|마리|송이|kg|g|ml|L|리터"
_QTY_RE = re.compile(rf"(\d+)\s*({_UNIT})?", re.IGNORECASE)
_DAY_RE = re.compile(r"(\d{1,2})\s*[/\-월.]\s*(\d{1,2})")
_TIME_RE = re.compile(r"(\d{1,2})\s*(?::|시)\s*(\d{1,2})?")
_SKIP_RE = re.compile(r"안\s?했|없어|없습니다|안했|건너|아니")

# 품목 이름에서 걷어낼 것들: 수량, 시각, 날짜말, 그리고 '만들었어요' 같은 서술어.
_NOISE_RE = re.compile(
    rf"\d+\s*(?:{_UNIT})"
    r"|\d{1,2}\s*[:시]\s*\d{0,2}\s*분?"
    r"|\d{1,2}\s*[/\-월.]\s*\d{1,2}\s*일?"
    r"|오늘|어제|그저께|그제|아침|점심|저녁|오전|오후|새벽"
    r"|만들었\S*|만들어\S*|만듦|구웠\S*|구움|굽고\S*|생산\S*|준비\S*|나왔\S*|뽑았\S*"
    r"|했어\S*|했습니다|했다|해서\S*|팔았\S*|판매\S*|\d+",
    re.IGNORECASE,
)
_PARTICLE_RE = re.compile(r"(?:은|는|이|가|을|를|도|만|랑|하고|와|과)$")


def item_from(text: str) -> str:
    """문장에서 품목 이름만 남긴다. 못 알아들으면 빈 문자열 — 지어내지 않는다.

    '소금빵 20개 만들었어요' → '소금빵'. 라우터는 빈 값이면 기록을 만들지 않고
    사장님에게 다시 물어본다. 못 알아들은 걸 '신메뉴' 같은 이름으로 저장하면
    그건 사장님이 만든 적 없는 생산 기록이 된다.
    """
    cleaned = _NOISE_RE.sub(" ", text or "")
    cleaned = re.sub(r"[^\w가-힣\s]", " ", cleaned)
    words = [_PARTICLE_RE.sub("", w) for w in cleaned.split()]
    words = [w for w in words if w]
    return " ".join(words[:3])


def qty_from(text: str) -> str:
    m = _QTY_RE.search(text or "")
    if not m:
        return ""
    return f"{m.group(1)}{m.group(2) or '개'}"


def day_from(text: str) -> str:
    t = text or ""
    if "그저께" in t or "그제" in t:
        return iso_day(-2)
    if "어제" in t:
        return iso_day(-1)
    m = _DAY_RE.search(t)
    if m:
        now = _now()
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
