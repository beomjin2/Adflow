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

**이 모듈이 내보내는 태그는 어느 경로로 나오든 영문이다.** Anima는 Danbooru 태그로
학습돼 한국어를 못 읽는다 — 한국어가 프롬프트에 들어가면 도움이 아니라 잡음이다.
프롬프트에 "영어로만"을 적는 것만으로는 안 지켜진다(스토리 문장 실측 통과율 9%).
그래서 `_split_by_script()`로 잘라내고, 잘린 게 있으면 한 번 되묻는다.
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
    "format (lowercase ENGLISH, spaces as underscores). Never output Korean words — "
    "translate every Korean concept into the tag Danbooru actually uses, or drop it. "
    "No explanations, no natural-language "
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


# 프롬프트로 "영어로만"을 아무리 적어도 GPT는 스토리 문장에서 한국어를 그대로 뱉는다.
# 실측(gpt-4o-mini, temperature=0): 스토리 9문장에서 곰·주방·반죽·혼자·새벽·빵·웃음·
# 눈을_감다 가 나왔고 검증 통과율이 9%였다. 그래서 되묻는다 — 무엇이 걸렸는지 알려주면
# 대부분 한 번에 고쳐 온다.
_RETRY_PROMPT = (
    "These are not English Danbooru tags: {bad}. "
    "Answer again with ONLY real English Danbooru tags (lowercase, underscores). "
    "Translate every Korean concept into the tag Danbooru actually uses, or drop it."
)


def _split_tags(raw: str) -> list[str]:
    return [t for t in (s.strip().strip(",") for s in (raw or "").replace("\n", ",").split(",")) if t]


def _split_by_script(candidates: list[str]) -> tuple[list[str], list[str]]:
    """(영문 태그, 그렇지 않은 것). Anima는 Danbooru 태그로 학습돼 한국어를 못 읽는다 —
    넣어 봐야 도움이 아니라 프롬프트를 흐리는 잡음이다. 부탁이 아니라 여기서 자른다."""
    english: list[str] = []
    other: list[str] = []
    for tag in candidates:
        (english if tag.isascii() else other).append(tag)
    return english, other


def _ask_tags(messages: list[dict]) -> str:
    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.openai_model, messages=messages, temperature=0,
    )
    return resp.choices[0].message.content or ""


def english_candidates(look: str, kind: str = "character") -> list[str]:
    """GPT가 낸 태그 후보 중 **영문인 것만**. 실존 검증은 하지 않는다.

    비영문이 섞이면 한 번만 되묻는다. 잘라내기만 하면 컷이 거의 비어 버리기 때문이다 —
    스토리 문장에서는 후보의 대부분이 한국어로 나온 적이 있다.
    """
    if not settings.openai_api_key or not (look or "").strip():
        return []
    messages = [
        {"role": "system", "content": _system_prompt(kind)},
        {"role": "user", "content": look},
    ]
    try:
        raw = _ask_tags(messages)
    except Exception:
        logger.exception("GPT 태그 생성 실패 — 화이트리스트로 폴백")
        return []

    english, other = _split_by_script(_split_tags(raw))
    if not other:
        return english

    logger.warning("태그에 비영문이 섞였습니다 — 재요청합니다: %s", ", ".join(other[:8]))
    try:
        retry_raw = _ask_tags(messages + [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": _RETRY_PROMPT.format(bad=", ".join(other))},
        ])
    except Exception:
        logger.exception("태그 재요청 실패 — 영문만 남기고 진행합니다")
        return english

    retried, still_other = _split_by_script(_split_tags(retry_raw))
    if still_other:
        logger.warning("재요청에도 비영문이 남아 버립니다: %s", ", ".join(still_other[:8]))
    return english + [t for t in retried if t not in english]


def generate_tags_via_llm(look: str, kind: str = "character") -> list[str]:
    """GPT로 묘사에서 Danbooru 태그 후보를 뽑고 실존·게시물수를 검증해 돌려준다.
    kind="character"는 외형 설명, "scene"은 네컷의 한 컷 문장(행동·소품·장소).
    OPENAI_API_KEY가 없거나 호출이 실패하면 빈 리스트(호출부가 화이트리스트로 폴백)."""
    return verify_tags(english_candidates(look, kind))


def tags_for_look(look: str, kind: str = "character") -> list[str]:
    """묘사를 Danbooru 태그 목록으로. **돌려주는 값은 언제나 영문이다.**

    세 단계로 내려간다:

    1. GPT 후보 중 **실존하고 2,000장 이상**인 태그 (`verify_tags`)
    2. 화이트리스트(`KEYWORD_TO_TAG`) 매칭 — 캐릭터 외형 어휘라 kind="scene"에서는 거의 빈다
    3. 검증은 못 통과했지만 **영문인** GPT 후보

    3단계는 네컷의 컷 문장처럼 어휘가 화이트리스트 밖일 때 쓴다. 예전에는 여기서
    호출부가 한국어 원문을 프롬프트에 그대로 넣었다. 지어낸 영문 태그(`salt_bread`)는
    모델이 "salt bread"로 읽기라도 하지만 한국어는 아무것도 되지 않는다 — 둘 다
    이상적이진 않아도 한쪽만 쓸모가 있다.
    """
    candidates = english_candidates(look, kind)
    verified = verify_tags(candidates)
    if verified:
        return verified
    matched, _unmatched = resolve_look_to_tags(look)
    if matched:
        return matched
    if candidates:
        logger.info("검증을 통과한 태그가 없어 영문 후보를 그대로 씁니다: %s", ", ".join(candidates[:8]))
    return candidates
