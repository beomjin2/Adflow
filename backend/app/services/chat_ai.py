"""대화 입력에서 값을 뽑아내는 규칙(생산 품목·수량·날짜·시각)과 캐릭터 프롬프트 조립.

채팅 응답은 아직 규칙 기반이다 — LLM을 붙이는 자리는 storyboard 쪽이고, 여기는
사장님이 한국어로 쓴 문장에서 숫자·품목·시각을 읽어내는 파서다.
"""

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.services.danbooru_tags import tags_for_look

# 서버는 UTC로 돈다. 그대로 쓰면 새벽 5시에 구운 빵이 '어제' 생산으로 기록된다 —
# 새벽에 굽는 가게가 많으니 여기서 한국 시간으로 고정한다.
KST = ZoneInfo("Asia/Seoul")


def _now() -> datetime:
    return datetime.now(timezone.utc).astimezone(KST)

# 4방향 뽑기는 지금 UI에서 빠져 있다(화이트보드: "당장 캐릭터 4방향 뽑기는 x").
# 태그는 실측해서 넣어둔 것이라 지우지 않는다 — 다시 붙일 때 그대로 쓴다.
VIEW_LABELS = ["정면", "좌측면", "우측면", "뒷면"]
# 실존 Danbooru 구도 태그만 쓴다(CLAUDE.md 5-1). "front view"류는 Danbooru에 없는 표현이다.
# Danbooru엔 좌/우를 가르는 태그가 없어 양 측면은 같은 태그다 — 좌우는 IP-Adapter 참조와 시드에 맡긴다.
VIEW_HINTS = {
    "정면": "straight-on, looking_at_viewer",
    "좌측면": "from_side, profile",
    "우측면": "from_side, profile",
    "뒷면": "from_behind",
}

# '연습용' 워크플로우가 이 태그 조합에 맞춰 조정돼 있다. 사장님이 쓴 설명 앞에 붙여
# 화풍을 고정한다 — 이걸 빼면 같은 모델에서도 그림 톤이 매번 달라진다.
STYLE_TAGS = "masterpiece, best quality, score_7, safe, solo, (chibi:1.3), full body, simple background"


def character_prompt(char, hint: str = "") -> str:
    """캐릭터 시트를 '연습용' 워크플로우의 프롬프트로 조립한다.

    Anima는 Danbooru 태그로 학습된 모델이라 한국어 문장을 그대로 넣으면 얼버무린다
    (CLAUDE.md 5-1, v4 12컷 실험). 설명을 실존 Danbooru 태그로 바꿔 넣고, 태그를
    하나도 못 뽑았을 때만 원문으로 폴백한다. STYLE_TAGS 접두어는 그대로 둔다.

    시트에서 무엇을 읽을지는 character_sheet.IMAGE_FIELDS 한 곳에서만 정한다 —
    외형·아웃핏·설명·나이·이름 다섯 칸. 능력·성별·퍼스널 키워드는 시트에만 남고
    그림 쪽으로 넘어가지 않는다. 라우터가 시트가 다 찬 뒤에만 여기까지 오게 막으므로
    described가 비는 경우는 없다(비면 태그도 프롬프트도 STYLE_TAGS뿐이다).
    """
    pieces = [STYLE_TAGS]
    part = character_part(char)
    if part:
        pieces.append(part)
    if hint:
        pieces.append(hint)
    return ", ".join(pieces)


def character_part(char) -> str:
    """시트의 IMAGE_FIELDS 다섯 칸 → 실존 Danbooru 태그 문자열.

    태그를 하나도 못 뽑으면 원문, 그것도 없으면 빈 문자열. 캐릭터 후보 프롬프트와
    네컷 프롬프트(comic_prompt)가 같은 캐릭터 태그를 쓰도록 여기 한 곳에서만 계산한다.
    """
    from app.services.character_sheet import IMAGE_FIELDS

    described = ", ".join(
        value for value in ((getattr(char, f, "") or "").strip() for f in IMAGE_FIELDS) if value
    )
    tags = tags_for_look(described) if described else []
    if tags:
        return ", ".join(tags)
    return described


# 네컷은 장소·소품 태그가 들어가므로 STYLE_TAGS의 simple background만 뺀다.
COMIC_STYLE_TAGS = "masterpiece, best quality, score_7, safe, solo, (chibi:1.3), full body"


def comic_prompt(char_part_text: str, cut_line: str) -> str:
    """네컷의 한 컷 프롬프트 — 캐릭터 태그 + 컷 문장을 태그로 바꾼 것.

    컷 문장("손님이 몰려온다")도 같은 변환을 거친다. 태그가 안 나오면 원문을 넣는다 —
    Anima가 얼버무릴 수 있지만 컷을 비워 두는 것보다 낫다. 캐릭터 정체성은 참조
    이미지(IP-Adapter)가 잡고, 여기 태그는 행동·소품·장소를 말한다.
    char_part_text는 character_part()로 한 번만 계산해 넘긴다(GPT 호출 절약).
    """
    scene = (cut_line or "").strip()
    scene_tags = tags_for_look(scene, kind="scene") if scene else []
    pieces = [COMIC_STYLE_TAGS, char_part_text, ", ".join(scene_tags) if scene_tags else scene]
    return ", ".join(p for p in pieces if p)


def pending_candidates(count: int = 3) -> list[dict]:
    """생성 대기 칸 count개. 이미지는 백그라운드 워커가 나중에 채운다."""
    return [
        {"label": f"후보{i + 1}", "image": None, "status": "generating"}
        for i in range(count)
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
_UNIT = (
    r"개|봉지|봉|판|장|잔|병|팩|박스|상자|세트|인분|마리|송이|다발|묶음|단|줄|통|포기"
    r"|근|컵|조각|그릇|접시|바구니|켤레|kg|g|ml|L|리터"
)
_QTY_RE = re.compile(rf"(\d+)\s*({_UNIT})?", re.IGNORECASE)
_DAY_RE = re.compile(r"(\d{1,2})\s*[/\-월.]\s*(\d{1,2})")
_TIME_RE = re.compile(r"(\d{1,2})\s*(?::|시)\s*(\d{1,2})?")
_SKIP_RE = re.compile(r"안\s?했|없어|없습니다|안했|건너|아니")

# 날짜·시각 표현. 품목을 찾기 전에 먼저 걷어낸다 — 안 그러면 '9/16에'의 9를 수량으로 읽는다.
_WHEN_RE = re.compile(
    r"\d{1,2}\s*[:시]\s*\d{0,2}\s*분?"
    r"|\d{1,2}\s*[/\-월.]\s*\d{1,2}\s*일?"
    r"|오늘|어제|그저께|그제|아침|점심|저녁|오전|오후|새벽",
    re.IGNORECASE,
)

# '만들었어요' 같은 서술어. 품목 이름이 아니다.
_VERB_RE = re.compile(
    r"만들었\S*|만들어\S*|만듦|구웠\S*|구움|굽고\S*|생산\S*|준비\S*|나왔\S*|뽑았\S*"
    r"|했어\S*|했습니다|했다|해서\S*|팔았\S*|판매\S*",
    re.IGNORECASE,
)

_PARTICLE_RE = re.compile(r"(?:은|는|이|가|을|를|도|만|랑|하고|와|과|에서|에|부터|까지|으로|로)$")

# '반찬가게인데', '날이 더워서' 처럼 배경을 설명하는 마디. 품목이 아니라 맥락이므로
# 어미만 떼지 말고 단어를 통째로 버린다 — 안 그러면 품목이 '반찬가게 멸치볶음'이 된다.
# '서'로 끝나는 말(더워서·바빠서·해서·가게에서)은 한국어에서 거의 다 이런 연결 어미다.
_CLAUSE_RE = re.compile(r"(?:인데요?|는데요?|한데|이고|이며|서)$")

# 뜻 없는 말버릇. 이게 남으면 '음 그냥 뭐'가 품목 이름으로 저장된다.
_FILLER = {
    "음", "어", "아", "응", "네", "예", "그냥", "뭐", "좀", "저기", "일단", "막",
    "그", "이", "저", "것", "거", "등", "및", "제가", "저희", "우리",
}


def item_from(text: str) -> str:
    """문장에서 품목 이름만 남긴다. 못 알아들으면 빈 문자열 — 지어내지 않는다.

    '소금빵 20개 만들었어요' → '소금빵'. 라우터는 빈 값이면 기록을 만들지 않고
    사장님에게 다시 물어본다. 못 알아들은 걸 '신메뉴' 같은 이름으로 저장하면
    그건 사장님이 만든 적 없는 생산 기록이 된다.

    품목은 업종마다 다르다(빵·반찬·꽃…). 그래서 품목 사전을 두지 않고 **수량을
    기준점으로** 삼는다 — 한국어에서 품목은 수량 바로 앞에 온다("소금빵 20개",
    "국화 30송이", "멸치볶음 15팩"). 수량이 아예 없으면 생산 기록으로 볼 수 없으니
    빈 문자열을 돌려주고 라우터가 되묻게 한다.
    """
    without_when = _WHEN_RE.sub(" ", text or "")
    qty = _QTY_RE.search(without_when)
    if not qty:
        # 수량이 없는 문장은 생산 기록이 아니다. '음 그냥 뭐 좀' 같은 말이
        # 품목으로 저장되는 걸 여기서 막는다.
        return ""

    def runs(segment: str) -> list[list[str]]:
        """살아남은 낱말을 '끊기지 않고 붙어 있는 덩어리' 단위로 묶어 돌려준다.

        덩어리로 묶는 이유 — '초코 소금빵'은 두 낱말이 붙어 있으니 한 품목이지만,
        '날이 더워서 팥빙수'는 사이에 버려진 말이 있으니 '날'과 '팥빙수'를 붙이면 안 된다.
        """
        segment = _VERB_RE.sub(" @ ", segment)
        segment = re.sub(r"[^\w가-힣\s@]", " @ ", segment)
        grouped: list[list[str]] = [[]]
        for word in segment.split():
            if word == "@" or _CLAUSE_RE.search(word):
                grouped.append([])
                continue
            word = _PARTICLE_RE.sub("", word)
            if not word or word in _FILLER or word.isdigit():
                grouped.append([])
                continue
            grouped[-1].append(word)
        return [g for g in grouped if g]

    # 수량 앞쪽을 먼저 본다 — 한국어는 품목이 수량 바로 앞에 온다.
    # 거기가 비면(수량을 먼저 말한 경우) 뒤쪽을 본다.
    before = runs(without_when[:qty.start()])
    if before:
        return " ".join(before[-1][-2:])
    after = runs(without_when[qty.end():])
    return " ".join(after[0][:2]) if after else ""


def qty_from(text: str) -> str:
    """수량. 날짜·시각을 먼저 걷어낸다 — '9/16에 김치 5통'에서 9를 수량으로 읽으면 안 된다."""
    m = _QTY_RE.search(_WHEN_RE.sub(" ", text or ""))
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
