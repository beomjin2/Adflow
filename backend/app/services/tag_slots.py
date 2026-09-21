"""태그를 슬롯에 담아 정해진 순서로 조립한다.

배경: 예전에는 STYLE_TAGS 뒤에 캐릭터 태그를 순서 없이 이어 붙였다. 그러면 두 가지가 샌다.

① **앵커가 없으면 사람이 된다.** `rabbit`은 Danbooru에서 동물 토끼와 '토끼귀 소녀'가
   섞여 있는 태그다. 2026-09-21 실측(seed 12345, 같은 시트로 5판): `no_humans,
   animal_focus, furry` 를 뺀 판에서만 흰 머리카락이 자라고 얼굴이 사람 쪽으로 넘어갔다.
② **구도 태그가 상수에 박혀 있으면 컷마다 못 바꾼다.** `full body`가 STYLE_TAGS에
   있으면 클로즈업을 시켜도 `full body, close-up`이 같이 나가 둘 다 무시된다.

그래서 슬롯을 **언제 바뀌는지**로 나눈다 — 전역(작품 단위) · 캐릭터(시트) · 컷(컷마다).
전역+캐릭터는 한 번 만들어 캐시하고, 컷 층만 갈아끼운다. 그래야 네 컷이 같은 캐릭터로 보인다.
"""

from __future__ import annotations

# ── 전역 상수 — 사람이 고를 일이 없는 값 ────────────────────────────────
QUALITY = "masterpiece, best quality, score_7"
RATING = "safe"

# 캐릭터를 '동물'로 못 박는다. 위 ①의 실측 근거로 기본값이 되었다.
ANCHOR = "no_humans, animal_focus, furry"

THEME_DEFAULT = "(chibi:1.3)"

# ── 슬롯 순서 — 조립은 이 순서로만 한다 ─────────────────────────────────
SLOT_ORDER = [
    "quality", "rating", "anchor", "theme",
    "species", "body", "face",
    "outfit_over", "outfit_top", "outfit_bottom", "outfit_neck", "marks",
    "shot_size", "shot_angle", "shot_count",
    "expression", "pose", "place",
]

# ── 태그를 슬롯에 넣는 표 ──────────────────────────────────────────────
# 여기 없는 태그는 'extra'로 가고, 캐릭터 슬롯 뒤 · 컷 슬롯 앞에 붙는다.
SPECIES = {"rabbit", "bear", "cat", "dog", "fox", "mouse", "bird",
           "animal_ears", "rabbit_ears", "cat_ears", "dog_ears", "bear_ears"}
BODY = {"plump", "fat", "slim", "muscular",
        "white_fur", "brown_fur", "black_fur", "grey_fur", "orange_fur",
        "yellow_fur", "pink_fur", "blue_fur", "purple_fur", "red_fur", "green_fur"}
FACE = {"heterochromia", "green_eyes", "purple_eyes", "blue_eyes", "red_eyes",
        "brown_eyes", "yellow_eyes", "pink_eyes", "black_eyes", "grey_eyes",
        "orange_eyes", "white_eyes", "closed_eyes"}
# 혼자 못 입는 옷 — 이게 있으면 상·하의를 같이 낸다(아래 SOLO_UNWEARABLE 참고).
OUTFIT_OVER = {"apron", "vest", "overalls", "jacket", "coat", "cardigan"}
OUTFIT_TOP = {"shirt", "sweater", "hoodie", "t-shirt", "blouse"}
OUTFIT_BOTTOM = {"pants", "shorts", "skirt"}
OUTFIT_NECK = {"scarf", "necktie", "bowtie", "ribbon", "bandana"}
MARKS = {"bandaid", "star_(symbol)", "heart_(symbol)", "eyepatch"}
SHOT_SIZE = {"full_body", "upper_body", "portrait", "close-up", "cowboy_shot", "wide_shot"}
SHOT_ANGLE = {"straight-on", "from_above", "from_below", "from_side", "from_behind", "dutch_angle"}
SHOT_COUNT = {"solo", "multiple_girls", "multiple_boys", "crowd", "2others"}
EXPRESSION = {"smile", "open_mouth", "closed_mouth", "surprised", "angry", "sad",
              "blush", "sparkling_eyes", "happy"}
POSE = {"standing", "sitting", "walking", "running", "waving", "arms_up",
        "hand_up", "holding", "lying"}
PLACE = {"simple_background", "white_background", "indoors", "outdoors",
         "cafe", "kitchen", "counter", "shop"}

# 색·무늬가 앞에 붙은 형태도 같은 슬롯으로 보낸다 — white_apron 은 apron 자리,
# striped_scarf 는 scarf 자리다. 빠뜨리면 extra 로 밀려 프롬프트 맨 뒤에 붙는다.
_COLOR_PREFIXES = ("white_", "black_", "brown_", "red_", "blue_", "green_",
                   "yellow_", "pink_", "purple_", "orange_", "grey_",
                   "striped_", "plaid_", "polka_dot_")

_SLOT_SETS = [
    ("species", SPECIES), ("body", BODY), ("face", FACE),
    ("outfit_over", OUTFIT_OVER), ("outfit_top", OUTFIT_TOP),
    ("outfit_bottom", OUTFIT_BOTTOM), ("outfit_neck", OUTFIT_NECK),
    ("marks", MARKS),
    ("shot_size", SHOT_SIZE), ("shot_angle", SHOT_ANGLE), ("shot_count", SHOT_COUNT),
    ("expression", EXPRESSION), ("pose", POSE), ("place", PLACE),
]

# 혼자 입을 수 없는 옷이 있으면 상·하의를 같이 낸다.
# 실측(2026-09-18, 시드 3개): 앞치마만 주면 모델이 밑옷을 지어내는데 그 색이 검정이다.
SOLO_UNWEARABLE = OUTFIT_OVER
DEFAULT_TOP = "white_shirt"
DEFAULT_BOTTOM = "brown_pants"


def _base(tag: str) -> str:
    """색 접두어를 떼어낸 이름. white_apron -> apron."""
    for p in _COLOR_PREFIXES:
        if tag.startswith(p):
            return tag[len(p):]
    return tag


def slot_of(tag: str) -> str:
    """태그가 어느 슬롯에 들어가는지. 모르면 'extra'."""
    t = tag.strip().replace(" ", "_")
    for name, members in _SLOT_SETS:
        if t in members or _base(t) in members:
            return name
    return "extra"


def to_slots(tags: list[str]) -> dict[str, list[str]]:
    """태그 목록을 슬롯별로 나눈다. 순서는 들어온 순서를 지킨다."""
    out: dict[str, list[str]] = {}
    for tag in tags:
        t = tag.strip().replace(" ", "_")
        if not t:
            continue
        out.setdefault(slot_of(t), [])
        if t not in out[slot_of(t)]:
            out[slot_of(t)].append(t)
    return out


def ensure_base_garments(slots: dict[str, list[str]]) -> dict[str, list[str]]:
    """겉옷만 있고 상·하의가 비었으면 기본값을 채운다.

    채우지 않으면 모델이 밑옷을 **검정으로** 지어낸다. 겉옷이 아예 없으면(목도리·반창고만)
    아무것도 넣지 않는다 — 동물은 맨털이 자연스럽고, 옷을 넣으면 오히려 사람처럼 된다.
    """
    has_over = any(_base(t) in SOLO_UNWEARABLE for t in slots.get("outfit_over", []))
    if not has_over:
        return slots
    if not slots.get("outfit_top"):
        slots["outfit_top"] = [DEFAULT_TOP]
    if not slots.get("outfit_bottom"):
        slots["outfit_bottom"] = [DEFAULT_BOTTOM]
    return slots


def assemble(slots: dict[str, list[str]], *, anchor: bool = True,
             theme: str = THEME_DEFAULT, quality: bool = True) -> str:
    """슬롯을 정해진 순서로 이어 붙인다. 비어 있는 슬롯은 그냥 건너뛴다."""
    parts: list[str] = []
    if quality:
        parts += [QUALITY, RATING]
    if anchor:
        parts.append(ANCHOR)
    if theme:
        parts.append(theme)
    for name in SLOT_ORDER:
        if name in ("quality", "rating", "anchor", "theme"):
            continue
        values = slots.get(name) or []
        if values:
            parts.append(", ".join(values))
    extra = slots.get("extra") or []
    if extra:
        parts.append(", ".join(extra))
    return ", ".join(p for p in parts if p)


def build(tags: list[str], **kw) -> str:
    """태그 목록 → 슬롯 정리 → 기본 의상 보정 → 조립. 호출부는 이것만 쓰면 된다."""
    return assemble(ensure_base_garments(to_slots(tags)), **kw)
