"""캐릭터 시트 대화에 붙는 LLM. 붙어 있지 않아도 서비스는 그대로 돈다.

하는 일은 두 가지뿐이다.

1. `read_fields()` — 사장님이 쓴 한 문장에서 **여러 칸**을 한 번에 읽어낸다.
   "앞치마 두른 3살 곰이요"를 외형·아웃핏·나이 세 칸으로 나눈다. 규칙 기반으로는
   이걸 못 해서 통째로 한 칸에 들어갔다.
2. `suggest_keywords()` — 퍼스널 키워드를 뽑는다. 정규식은 관형형만 겨우 집어내는데,
   여기서는 문장의 뜻을 보고 고를 수 있다.

**둘 다 실패해도 된다.** 키가 없거나, 네트워크가 끊겼거나, 응답이 이상하면 빈 값을
돌려주고 라우터가 규칙 기반 경로로 간다. 사장님 화면에는 아무 일도 일어나지 않는다 —
그림 생성과 달리 이건 없어도 대화가 이어지는 보조 장치다.

지어내지 않게 하는 것이 이 파일의 핵심이다. 프롬프트가 "사장님이 실제로 말한 것만"을
반복해서 요구하고, 받은 값도 아래에서 한 번 더 거른다. 사장님이 말한 적 없는 설정이
시트에 들어가면 그건 사장님 캐릭터가 아니다.
"""

import json
import logging

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

# 시트에서 LLM이 채울 수 있는 칸. 퍼스널 키워드는 따로 다룬다(자동 제안 흐름).
_FILLABLE = ["look", "outfit", "desc", "abilities", "age", "gender", "name"]

_EXTRACT_SYSTEM = """\
너는 한국 소상공인 사장님이 가게 마스코트 캐릭터를 만드는 걸 돕는다.
사장님이 방금 한 말에서 아래 캐릭터 시트 칸에 해당하는 내용만 뽑아 JSON으로 돌려준다.

칸:
- look: 외형. 종류·몸집·색·눈매처럼 눈에 보이는 생김새.
- outfit: 아웃핏. 입은 옷, 앞치마, 모자, 장신구.
- desc: 설명. 성격이나 가게에서 맡은 역할.
- abilities: 능력. 잘하는 일, 특기.
- age: 나이. "3살", "어린", "나이 든" 같은 표현 그대로.
- gender: 성별. 정하지 않겠다는 뜻이면 "없음".
- name: 이름. 캐릭터를 부르는 이름.

규칙:
1. 사장님이 실제로 말한 것만 넣는다. 말하지 않은 칸은 JSON에서 아예 뺀다.
2. 절대 지어내거나 추측하지 않는다. 그럴듯하게 채우지 않는다.
3. 값은 사장님이 쓴 한국어 표현을 최대한 그대로 살린다. 요약하거나 다듬지 않는다.
4. 한 문장에 여러 칸이 섞여 있으면 나눠서 각 칸에 넣는다.
5. 사장님 말이 어느 칸인지 불분명하면 지금 묻고 있는 칸에 넣는다.

출력은 이 모양의 JSON만: {"fields": {"look": "...", "age": "..."}}
해당하는 게 하나도 없으면 {"fields": {}}
"""

_KEYWORDS_SYSTEM = """\
너는 한국 소상공인 사장님이 만든 가게 마스코트 캐릭터의 퍼스널 키워드를 정한다.

사장님이 적은 캐릭터 시트를 보고, 이 캐릭터의 성격을 나타내는 키워드를 3~5개 뽑는다.

규칙:
1. 사장님이 적은 내용에서만 뽑는다. 시트에 근거가 없는 성격은 넣지 않는다.
2. 한국어 형용사나 짧은 명사구로 쓴다. 예: "느긋한", "다정한", "장난기 많은".
3. 외모 묘사(갈색, 통통한)보다 성격을 우선한다.
4. 뽑을 근거가 부족하면 억지로 채우지 말고 적게 낸다. 하나도 없으면 빈 목록.

출력은 이 모양의 JSON만: {"keywords": ["느긋한", "다정한"]}
"""


def available() -> bool:
    """LLM을 쓸 수 있는가. 키가 없으면 조용히 규칙 기반으로 돈다."""
    return bool(settings.openai_api_key)


def _ask(system: str, user: str) -> dict:
    """LLM에 묻고 JSON을 받는다. 무엇이 잘못되든 빈 dict — 대화를 막지 않는다."""
    if not available():
        return {}
    try:
        response = requests.post(
            f"{settings.openai_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openai_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0,
            },
            timeout=settings.openai_timeout_seconds,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else {}
    except Exception as exc:  # 네트워크·인증·응답 형식 무엇이든
        # 키를 로그에 흘리지 않는다 — 예외 문자열에 URL은 남아도 헤더는 남지 않는다.
        logger.warning("시트 LLM 호출 실패, 규칙 기반으로 진행합니다: %s", type(exc).__name__)
        return {}


def _sheet_summary(char) -> str:
    from app.services import character_sheet as sheet

    lines = []
    for field in sheet.ORDER:
        value = sheet.value_of(char, field)
        lines.append(f"- {sheet.LABELS[field]}({field}): {value or '(아직 비어 있음)'}")
    return "\n".join(lines)


def read_fields(char, text: str, asked_field: str = "") -> dict[str, str]:
    """사장님 문장에서 채울 칸들을 읽어낸다. 못 하면 빈 dict.

    돌려주는 값은 전부 사장님 문장에 실제로 있던 말이어야 한다. 아래에서 한 번 더
    거른다 — 모델이 규칙을 어기고 빈 칸을 채우려 드는 경우가 있다.
    """
    from app.services import character_sheet as sheet

    if not available() or not (text or "").strip():
        return {}

    asked_label = sheet.LABELS.get(asked_field, "")
    prompt = (
        f"지금까지 채워진 캐릭터 시트:\n{_sheet_summary(char)}\n\n"
        f"지금 묻고 있는 칸: {asked_label or '(없음)'}\n\n"
        f"사장님이 방금 한 말:\n{text.strip()}"
    )
    parsed = _ask(_EXTRACT_SYSTEM, prompt)
    fields = parsed.get("fields")
    if not isinstance(fields, dict):
        return {}

    cleaned: dict[str, str] = {}
    for field, value in fields.items():
        if field not in _FILLABLE or not isinstance(value, str):
            continue
        value = value.strip()
        if not value:
            continue
        # 모델이 길게 늘여 쓴 경우를 막는다. 사장님이 한 줄 말했는데 세 줄이 돌아오면
        # 그건 요약이 아니라 창작이다.
        if len(value) > len(text) + 40:
            continue
        # 지금 묻고 있는 칸이 아니면, 사장님 문장에 근거가 있어야 받는다.
        # 프롬프트로 "지어내지 마라"를 아무리 적어도 모델은 빈 칸을 채우려 든다 —
        # 실제로 "소금빵을 잘 구워요" 한마디에 성별과 이름까지 지어내는 걸 봤다.
        if field != asked_field and not _grounded(value, text):
            logger.info("근거 없는 칸 '%s'을(를) 버렸습니다", field)
            continue
        cleaned[field] = value
    return cleaned


def _grounded(value: str, text: str) -> bool:
    """값이 사장님 문장에 실제로 뿌리를 두고 있는가.

    통째로 같기를 요구하면 너무 빡빡하다 — "소금빵을 잘 구워요"에서 능력을 뽑으면
    "소금빵 굽기"가 되는 게 자연스럽다. 그래서 두 글자 이상 겹치는 조각이 있으면
    근거가 있다고 본다. "남성"·"구름이"처럼 문장에 흔적조차 없는 말은 여기서 걸린다.
    """
    haystack = text.replace(" ", "")
    return any(
        value[i:i + 2] in haystack
        for i in range(max(len(value) - 1, 1))
        if len(value[i:i + 2]) == 2
    )


def suggest_keywords(char, limit: int = 5) -> list[str]:
    """퍼스널 키워드를 뽑는다. 못 하면 빈 목록 — 호출부가 정규식 추출로 되돌아간다."""
    if not available():
        return []
    parsed = _ask(_KEYWORDS_SYSTEM, f"캐릭터 시트:\n{_sheet_summary(char)}")
    words = parsed.get("keywords")
    if not isinstance(words, list):
        return []
    return [w.strip() for w in words if isinstance(w, str) and w.strip()][:limit]
