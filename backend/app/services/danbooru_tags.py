"""캐릭터 외형 설명(한국어)을 실존 Danbooru 태그 목록으로 바꾼다.

배경: Anima는 Danbooru 태그로 학습된 모델이라, 자연어 문장("귀여운 곰 마스코트
일러스트...")을 넣으면 얼버무리거나 화풍이 흔들린다. chat_ai.character_prompt()가
STYLE_TAGS 뒤에 붙일 설명 부분을 여기서 태그로 만든다.

주 경로: generate_tags_via_llm() — GPT가 묘사에서 태그 후보를 뽑고,
danbooru_lookup.verify_tags()로 실존·게시물수(2,000장 이상)를 검증한다. 사전을
손으로 넓혀야 하는 KEYWORD_TO_TAG(아래)와 달리 어떤 묘사든 대응 가능하다.

폴백 경로: OPENAI_API_KEY가 없거나 GPT 호출이 실패하면 KEYWORD_TO_TAG 화이트리스트
(출처: research/34·35, Jio7/danbooru-tags-classified 대조 확인)로 대체한다. 이쪽은
사전에 없는 단어를 절대 지어내지 않고 버린다.
"""

from __future__ import annotations

import logging

from openai import OpenAI

from app.core.config import settings
from app.services.danbooru_lookup import verify_tags

logger = logging.getLogger(__name__)

KEYWORD_TO_TAG: dict[str, str] = {
    # 종(species)
    "토끼": "rabbit", "rabbit": "rabbit",
    "곰": "bear", "bear": "bear",
    "고양이": "cat", "cat": "cat",
    "강아지": "dog", "개": "dog", "dog": "dog",

    # 귀
    "동물귀": "animal ears", "짐승귀": "animal ears",

    # 털색
    "하얀": "white fur", "흰": "white fur", "white": "white fur",
    "밀색": "tan fur", "베이지": "tan fur",
    "갈색": "brown fur",
    "검은": "black fur", "검정": "black fur",

    # 눈
    "짝눈": "heterochromia", "이색눈": "heterochromia",
    "초록눈": "green eyes", "녹색눈": "green eyes",
    "보라눈": "purple eyes", "자주눈": "purple eyes",
    "파란눈": "blue eyes",
    "둥근눈": "round eyes",

    # 체형/화풍
    "통통한": "plump", "뚱뚱한": "plump",
    "치비": "chibi", "미니": "chibi",

    # 의상/소품
    "목도리": "scarf",
    "줄무늬목도리": "striped scarf",
    "빨간목도리": "red scarf",
    "반창고": "bandaid", "밴드": "bandaid",
    "별무늬": "star (symbol)", "별": "star (symbol)",
    "앞치마": "apron",
    "밀가루": "flour",  # 확인 필요 — post count 미검증, 사용 전 재확인 권장
}


def resolve_look_to_tags(look: str) -> tuple[list[str], list[str]]:
    """(매칭된 태그 목록, 버려진 원문 단어 목록)을 반환한다."""
    matched: list[str] = []
    unmatched: list[str] = []
    seen: set[str] = set()

    raw_tokens = [t.strip() for t in (look or "").replace(",", " ").replace(".", " ").split() if t.strip()]
    for token in raw_tokens:
        tag = KEYWORD_TO_TAG.get(token)
        if tag is None:
            tag = next((v for k, v in KEYWORD_TO_TAG.items() if k in token), None)
        if tag:
            if tag not in seen:
                matched.append(tag)
                seen.add(tag)
        else:
            unmatched.append(token)
    return matched, unmatched


_LLM_SYSTEM_PROMPT = (
    "You convert a short character description into Danbooru imageboard tags. "
    "Output ONLY a comma-separated list of real Danbooru tags in their exact tag "
    "format (lowercase, spaces as underscores). No explanations, no natural-language "
    "phrases. If a concept has no real Danbooru tag, omit it rather than inventing one. "
    "Danbooru's exact vocabulary is often not the literal translation — prefer the "
    "tag actually used on the site over a made-up compound, and keep color/size "
    "modifiers as separate tags rather than dropping them. Examples: "
    "'chubby character' -> plump (NOT chubby); "
    "'mismatched eye colors' -> heterochromia; "
    "'white rabbit' -> rabbit, white_fur (NOT white_rabbit); "
    "'star-shaped mark' -> star_(symbol) (NOT star_pattern/star_mark); "
    "'small cute proportions' -> chibi; "
    "'bandage/plaster on skin' -> bandaid (NOT bandage); "
    "'red scarf' -> scarf, red_scarf (keep both, do not drop the color)."
)

# 네컷의 한 컷 문장(장면) 전용. 캐릭터용 프롬프트를 그대로 쓰면 GPT가 한국어 단어를
# 그대로 뱉거나(빵집, 빈 진열대) 없는 태그를 지어낸다(salt_bread). 예시는 전부 parquet에서
# 2,000장 이상 확인한 태그다. "비어 있음"은 태그가 없으므로 물체+반응으로, 손님은 동물로 옮긴다.
_SCENE_SYSTEM_PROMPT = (
    "You convert one Korean sentence describing a scene in a 4-panel bakery mascot comic "
    "into Danbooru imageboard tags for the mascot's ACTION, EXPRESSION, PROPS and PLACE. "
    "Output ONLY a comma-separated list of real Danbooru tags in exact tag format "
    "(lowercase English, spaces as underscores). Never output Korean words, never invent "
    "compound tags, never describe the mascot's appearance (it is given elsewhere). "
    "If a concept has no real Danbooru tag, express it with tags that do exist. Examples: "
    "'갓 구운 빵이 진열된다' -> bread, food, tray, steam, shop, indoors; "
    "'오븐에서 빵을 꺼낸다' -> holding_tray, tray, bread, steam, kitchen; "
    "'손님들이 빵집으로 몰려온다' -> multiple_others, crowd, cat, dog, shop, indoors; "
    "'진열대가 텅 비었다 / 다 팔렸다' -> tray, plate, looking_down, looking_at_object, surprised, open_mouth, sweatdrop, indoors "
    "(no bread tag — emptiness is shown by the empty tray and the reaction); "
    "'빵을 들고 손을 흔든다' -> holding_food, bread, waving, arm_up, smile, shop; "
    "'턱을 짚고 고민한다' -> hand_on_own_chin, head_tilt, thinking; "
    "'기뻐서 눈을 반짝인다' -> happy, sparkling_eyes, smile; "
    "'지쳐서 땀을 흘린다' -> sweatdrop, shaded_face, half-closed_eyes."
)


def _system_prompt(kind: str) -> str:
    return _SCENE_SYSTEM_PROMPT if kind == "scene" else _LLM_SYSTEM_PROMPT


def generate_tags_via_llm(look: str, kind: str = "character") -> list[str]:
    """GPT로 묘사에서 Danbooru 태그 후보를 뽑고 실존·게시물수를 검증해 돌려준다.
    kind="character"는 외형 설명, "scene"은 네컷의 한 컷 문장(행동·소품·장소).
    OPENAI_API_KEY가 없거나 호출이 실패하면 빈 리스트(호출부가 화이트리스트로 폴백)."""
    if not settings.openai_api_key or not (look or "").strip():
        return []
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _system_prompt(kind)},
                {"role": "user", "content": look},
            ],
            temperature=0,
        )
        raw = resp.choices[0].message.content or ""
    except Exception:
        logger.exception("GPT 태그 생성 실패 — 화이트리스트로 폴백")
        return []
    candidates = [t.strip() for t in raw.replace("\n", ",").split(",") if t.strip()]
    return verify_tags(candidates)


def tags_for_look(look: str, kind: str = "character") -> list[str]:
    """묘사를 실존 Danbooru 태그 목록으로. GPT(검증 포함)가 1순위, 실패하면 화이트리스트.
    화이트리스트는 캐릭터 외형 어휘라 kind="scene"에서는 거의 비어 돌아온다(호출부가 원문 폴백)."""
    tags = generate_tags_via_llm(look, kind)
    if tags:
        return tags
    matched, _unmatched = resolve_look_to_tags(look)
    return matched
