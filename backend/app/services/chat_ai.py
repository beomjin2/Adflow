"""캐릭터 프롬프트 조립과 생성 대기 칸 만들기.

예전엔 대화 입력에서 생산 품목·수량·날짜·시각을 읽어내는 정규식 파서도 여기 있었다
(대화 첫 마디를 생산 기록으로 파싱하던 기능) — 생산 기록은 "내 정보 > 생산 기록"
탭에서만 남기기로 하면서 그 파서는 더는 안 쓴다.
"""

import logging

from app.services.danbooru_lookup import verify_tags
from app.services.danbooru_tags import tags_for_look

logger = logging.getLogger(__name__)

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

    시트에서 무엇을 읽을지는 character_sheet.IMAGE_FIELDS 한 곳에서만 정한다.
    라우터가 시트가 다 찬 뒤에만 여기까지 오게 막으므로 described가 비는 경우는 없다
    (비면 태그도 프롬프트도 STYLE_TAGS뿐이다).
    """
    pieces = [STYLE_TAGS]
    part = character_part(char)
    if part:
        pieces.append(part)
    if hint:
        pieces.append(hint)
    return ", ".join(pieces)


# 시트 칸 → 태그 변환기에 줄 영문 라벨. 칸을 쉼표로 이어 붙여 한 덩어리로 넘기면
# GPT가 어느 말이 생김새이고 어느 말이 성격인지 가르지 못한다 — 실제로 이름("구웅이")과
# 설명 문장이 외형 묘사에 섞여 들어가 프롬프트를 흐렸다. 라벨을 붙여 칸마다 무엇으로
# 바꿀지 알려주면 시트에 적힌 게 빠짐없이 태그가 된다.
_IMAGE_LABEL = {
    "look": "APPEARANCE",
    "outfit": "CLOTHING",
    "age": "AGE",
    "desc": "PERSONALITY",
    "abilities": "SKILL",
    "keywords": "MOOD",
}


# 혼자 입을 수 없는 겉옷. 이것만 있고 속에 입을 옷이 없으면 그림 모델이 밑에 입을 옷을
# 알아서 채워 넣는데, 실측(2026-09-18, 시드 3개)으로는 그 색이 검정이다.
_LAYER_GARMENTS = ("apron", "vest", "overalls", "jacket", "coat", "cardigan", "cape", "suspenders")
# 속에 입는 옷. 이 계열이 하나라도 있으면 **사장님이 이미 정한 것**이라 건드리지 않는다.
_INNER_GARMENTS = ("shirt", "pants", "shorts", "skirt", "dress", "sweater", "blouse",
                   "trousers", "jeans", "robe", "kimono", "uniform")

# 사장님이 "그냥 털 위에 앞치마만"을 고른 셈일 때, 모델이 지어내려는 옷을 막는 말.
_INVENTED_INNER = "shirt, pants, shorts, skirt, dress, black_shirt, black_pants"


def clothing_negative(tag_text: str) -> str:
    """겉옷만 정해졌을 때 그림 모델이 **속에 입을 옷을 지어내지 못하게** 막는 네거티브.

    사장님이 "앞치마"만 말했으면 앞치마만 그려야 한다. 그런데 앞치마·조끼처럼 혼자 입을
    수 없는 옷만 주면 모델이 밑에 입을 옷을 채워 넣고 그 색이 검정이다.

    예전에는 이걸 **positive에 흰 셔츠와 갈색 바지를 박아 넣어** 막았다. 그러면 사장님이
    말한 적 없는 옷이 캐릭터에 그대로 붙는다 — 정하는 건 사장님 몫인데 우리가 정해 버린
    것이다. 여기서는 옷을 더하지 않고 **막기만** 한다. 결과는 털 위에 앞치마만 두른
    모습이고, 그게 사장님이 적은 그대로다.

    속에 입을 옷을 이미 말했으면 아무것도 하지 않는다 — 그건 사장님이 정한 것이다.
    (무엇을 입을지 물어보는 건 대화 쪽 몫이다: character_sheet.QUESTIONS['outfit'])

    네컷에는 쓰지 않는다. 그쪽 워크플로우는 cfg 1.0이라 네거티브가 사실상 안 듣고,
    옷은 확정한 캐릭터 그림을 참조(IP-Adapter)해서 따라온다.
    """
    tags = tag_text or ""
    if not any(word in tags for word in _LAYER_GARMENTS):
        return ""
    if any(word in tags for word in _INNER_GARMENTS):
        return ""
    return _INVENTED_INNER


# 네컷에서 캐릭터를 고정할 때 쓰는 칸. 성격·능력·키워드는 뺀다 — 컷마다 표정과 행동이
# 따로 정해지는데(comic_prompt의 scene 태그) 캐릭터 태그에 고정 표정이 섞이면 두 지시가
# 부딪쳐 슬픈 컷에서도 웃는다. 네컷에서 정체성은 생김새·옷·나이로 잡고, 나머지는
# 참조 이미지(IP-Adapter)가 잡는다.
COMIC_IDENTITY_FIELDS = ["look", "outfit", "age"]


def character_sheet_text(char, fields: list[str] | None = None) -> str:
    """시트 칸을 라벨 붙은 여러 줄로. 빈 칸은 줄 자체를 내지 않는다."""
    from app.services.character_sheet import IMAGE_FIELDS, value_of

    lines = []
    for field in (fields or IMAGE_FIELDS):
        label = _IMAGE_LABEL.get(field)
        value = value_of(char, field)
        if label and value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def character_part(char, fields: list[str] | None = None) -> str:
    """시트 칸 → 실존 Danbooru 태그 문자열.

    태그를 하나도 못 뽑으면 **빈 문자열**이다. 예전에는 한국어 원문을 그대로 넣었는데,
    Anima는 Danbooru 태그로 학습돼 한국어를 못 읽는다 — 설명이 아니라 잡음이 하나 더
    붙을 뿐이었다.

    fields를 안 주면 시트의 IMAGE_FIELDS 전부(캐릭터 후보용)다. 네컷은
    COMIC_IDENTITY_FIELDS를 넘겨 표정·소품을 빼고 부른다.
    """
    described = character_sheet_text(char, fields)
    tags = tags_for_look(described) if described else []
    if tags:
        return ", ".join(tags)
    if described:
        logger.warning(
            "캐릭터 태그를 하나도 못 뽑았습니다 — 설명 없이 갑니다: %s",
            described.replace("\n", " / ")[:80],
        )
    return ""


# 네컷은 장소·소품 태그가 들어가므로 STYLE_TAGS의 simple background만 뺀다.
COMIC_STYLE_TAGS = "masterpiece, best quality, score_7, safe, solo, (chibi:1.3), full body"


def comic_prompt(char_part_text: str, cut_line: str, camera: str = "") -> str:
    """네컷의 한 컷 프롬프트 — 캐릭터 태그 + 컷 문장을 태그로 바꾼 것 (+ 구도 태그).

    컷 문장("손님이 몰려온다")도 같은 변환을 거친다. **태그가 안 나와도 한국어 원문을
    넣지 않는다** — 예전에는 "컷을 비워 두는 것보다 낫다"고 원문을 넣었지만, Anima는
    Danbooru 태그로 학습돼 한국어를 못 읽으므로 비워 두는 것과 결과가 같고 프롬프트만
    흐려진다. tags_for_look()이 검증을 못 통과한 영문 후보까지 내려가며 찾아 주므로
    여기까지 비는 일은 GPT 호출 자체가 실패했을 때뿐이다.
    캐릭터 정체성은 참조 이미지(IP-Adapter)가 잡고, 여기 태그는 행동·소품·장소를 말한다.
    char_part_text는 character_part()로 한 번만 계산해 넘긴다(GPT 호출 절약).
    camera는 스토리 제안이 고른 구도 태그(straight-on 등) — 실존 검증을 통과할 때만 붙인다.
    """
    scene = (cut_line or "").strip()
    scene_tags = tags_for_look(scene, kind="scene") if scene else []
    if scene and not scene_tags:
        logger.warning("컷 태그를 못 뽑았습니다 — 컷 문장 없이 갑니다: %s", scene[:60])
    cam = verify_tags([camera]) if camera else []
    pieces = [COMIC_STYLE_TAGS, char_part_text, ", ".join(scene_tags), ", ".join(cam)]
    return ", ".join(p for p in pieces if p)


# ── 연출 슬롯 경로 (2026-09-22). 접두어에서 `solo, full body`를 뺐다 — 둘은 컷마다 바뀌는 슬롯
# (count·size)이라 접두어에 고정하면 "멀리서" 컷도 전신 클로즈업이 됐다(09-21 실측 20/20 가운데 고정).
COMIC_GLOBAL_TAGS = "masterpiece, best quality, score_7, safe, (chibi:1.3)"

# 닫힌 슬롯 — 한국어 선택지 → 실존 Danbooru 태그(전부 2,000장 이상 확인). GPT 없이 표로 바꾼다.
SHOT_SIZE = {"아주작게": "wide_shot", "작게": "full_body", "보통": "cowboy_shot", "크게": "upper_body", "아주크게": "close-up"}
SHOT_ANGLE = {"정면": "straight-on", "위에서": "from_above", "아래에서": "from_below", "옆에서": "from_side", "뒤에서": "from_behind"}
SHOT_COUNT = {"혼자": "solo", "여럿": "multiple_others"}
# 시선. 정면(카메라 응시)만 쓰면 증명사진이 된다 — 연출이 네 컷 중 한 컷만 카메라를 보게 고른다.
GAZE = {"정면": "looking_at_viewer", "옆": "looking_to_the_side", "아래": "looking_down",
        "상대": "looking_at_another", "눈감음": "closed_eyes"}
# 위치(왼쪽·가운데·오른쪽)는 태그가 없다(사전에 없음, 09-18 실측 33%). 넓게 뽑아 자르는 방식(image_gen.POSITION_CROP).
OPEN_SLOTS = ("expression", "pose", "place", "props", "light")


def comic_prompt_slots(char_part_text: str, slots: dict) -> tuple[str, dict]:
    """연출 슬롯 → 한 컷 프롬프트. (프롬프트, 계단별 기록). 전역 + 캐릭터(4컷 고정) + 컷 슬롯(변함).
    닫힌 슬롯은 표로, 열린 슬롯은 칸 이름을 붙여 슬롯 전용 태거(kind="slot")로 1~3개씩. 같은 태그는 한 번만."""
    trace: dict = {"closed": {}, "open": {}}
    parts: list[str] = [COMIC_GLOBAL_TAGS, char_part_text]
    shot = slots.get("shot") or {}
    for key, table in (("size", SHOT_SIZE), ("angle", SHOT_ANGLE), ("count", SHOT_COUNT)):
        val = str(shot.get(key) or "").strip()
        tag = table.get(val, "")
        trace["closed"][f"shot.{key}"] = {"in": val, "tag": tag, "ok": bool(tag)}
        if tag:
            parts.append(tag)
    gaze_in = str(slots.get("gaze") or "").strip()
    gaze_tag = GAZE.get(gaze_in, "")
    trace["closed"]["gaze"] = {"in": gaze_in, "tag": gaze_tag, "ok": bool(gaze_tag)}
    if gaze_tag:
        parts.append(gaze_tag)
    pos = str(shot.get("position") or "").strip()
    trace["closed"]["shot.position"] = {"in": pos, "tag": "", "ok": bool(pos), "how": "넓게 뽑아 자름" if pos else ""}
    for key in OPEN_SLOTS:
        raw = slots.get(key)
        text = ", ".join(str(x) for x in raw) if isinstance(raw, list) else str(raw or "")
        text = text.strip()
        tags = tags_for_look(f"{key}: {text}", kind="slot") if text else []
        trace["open"][key] = {"in": text, "tags": tags}
        if tags:
            parts.append(", ".join(tags))
    seen: set[str] = set()
    tokens: list[str] = []
    for p in parts:
        for tok in (x.strip() for x in p.split(",")):
            if tok and tok not in seen:
                seen.add(tok)
                tokens.append(tok)
    prompt = ", ".join(tokens)
    trace["prompt"] = prompt
    return prompt, trace


def pending_candidates(count: int = 3) -> list[dict]:
    """생성 대기 칸 count개. 이미지는 백그라운드 워커가 나중에 채운다."""
    return [
        {"label": f"후보{i + 1}", "image": None, "status": "generating"}
        for i in range(count)
    ]


def new_pid() -> str:
    import random
    import time
    return f"p{int(time.time() * 1000)}{random.randint(1000, 9999)}"
