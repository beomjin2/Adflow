"""스토리보드 대화에 붙는 LLM. 붙어 있지 않아도 서비스는 그대로 돈다.

하는 일은 둘이다 — `plan_from_text()` 가 사장님이 쓴 말을 **광고 컷 구성**으로
나누고, `generate_caption()` 이 확정된 컷으로 인스타에 올릴 캡션을 따로 쓴다(컷
대사는 말풍선용 40자 제한이 있어 그대로 이어붙이면 SNS 톤이 안 살아서다).
plan_from_text 는 전에는 정규식이 문장부호에서 잘랐다(`_cuts_from_text`). 그건 컷 구성이 아니라
사장님 문장을 토막낸 것이다 — "오늘 소금빵 30개 구웠어요" 는 한 컷이 되고, 그 한 컷이
그대로 그림 프롬프트로 들어가 글자를 못 쓰는 모델에게 대사를 그리라고 시켰다.

`line` 은 말풍선에 들어갈 대사고 `action` 은 그림에 들어갈 동작이다. 둘을 나눠야
`_start_cuts()` 가 그림에는 동작만 넣는다.

밈도 여기서 같이 본다(예전엔 meme_ai.py가 밈 카드+가게 정보로 스토리를 따로 만드는
별도 경로였다 — 대화와 밈이 따로 놀아서 사장님이 뭘 눌러야 밈이 들어가는지 헷갈렸다).
트렌드 확인 화면에서 미리 골라 온 밈이 있을 때만(`trend_meme`) 참고한다 — 안 골랐으면
밈 얘기 자체를 꺼내지 않는다. GPT가 크롤링된 밈 중에서 스스로 골라 끼워 넣게 하면
사장님이 고른 적 없는 밈이 광고에 섞일 수 있어서다.

**실패해도 된다.** 키가 없거나 네트워크가 끊겼거나 응답이 이상하면 `None` 을 돌려주고
라우터가 규칙 기반(`_cuts_from_text`)으로 간다. sheet_llm 과 같은 약속이다.

돌려주는 값 세 가지를 구분한다:
  None  — LLM을 못 썼다. 호출부가 규칙 기반으로 돌아간다.
  {"cuts": [], "meme_used": None}
        — LLM이 "알릴 거리가 아예 없다"라고 판단했다(인사·되레 묻는 말·"몰라").
          호출부는 지어내지 말고 되물어야 한다.
          **"오픈시간" 같은 한 단어는 여기 해당하지 않는다** — 그건 알릴 거리이므로
          가게 정보에 적힌 값으로 컷을 만든다. 되묻기는 소재가 없을 때만이다.
  {"cuts": [...], "meme_used": {"id","name"} | None}
        — 컷 구성. meme_used는 실제로 반영한 밈(있으면).
"""

import json
import logging
import re

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

# 그림 모델이 알아듣는 구도 태그만 허용한다. 자연어 카메라 지시("입구 클로즈업")는 여기로 매핑된다.
CAMERA_TAGS = ("straight-on", "close-up", "from_side", "from_below", "from_above", "wide_shot")

_PLAN_SYSTEM = """\
너는 한국 동네 가게 사장님의 SNS 광고를 같이 만든다.
사장님이 방금 한 말을 광고 컷 구성으로 나눠 JSON으로 돌려준다.

컷 하나는 이렇게 만든다:
- line: 말풍선이나 자막에 들어갈 한국어 한 문장. 짧게 — 40자를 넘기지 않는다.
- action: 그 컷의 **그림**에 들어갈 동작. 마스코트가 하는 행동·표정·소품·장소를
  한국어 한 문장으로 적는다. 대사도 글자도 넣지 않는다 — 그림 모델은 글자를 못 쓴다.
- camera: 다음 중 하나 — {cameras}. 고를 게 없으면 빈 문자열.

규칙:
1. **사장님이 말한 내용이 광고의 중심이다.** 말한 적 없는 사실은 지어내지 않는다.
   가격·할인율·수량·시간은 사장님 말이나 아래 가게 정보에 적혀 있을 때만 쓴다.
2. 가게 정보에 있는 값(업종·주소·영업시간·소개)은 그대로 써도 된다. 비어 있는 칸은 쓰지 않는다.
3. 마지막 컷은 실제로 적혀 있는 가게 정보로 끝낸다 — 영업시간이나 가게 소개처럼.
   적혀 있는 게 없으면 사장님이 말한 내용으로 끝낸다.
4. 주인공은 가게 마스코트 하나다. 사람 손님은 그리지 않는다 — 손님이 필요하면 동물 손님으로 적는다.
5. 광고 느낌(컨셉)을 대사 **말투**에 반영한다. 느낌을 설명하는 문장을 쓰지 않는다.
6. 컷은 정확히 {n}개.
{meme_rule}

출력은 이 모양의 JSON만:
{{"cuts": [{{"n": 1, "line": "...", "action": "...", "camera": "..."}}], "meme_used": 실제로 반영한 밈의 id(문자열) 또는 null}}
만들지 되물을지는 하나로 가른다 — **사장님 말에서 "무엇을" 알릴지가 집히는가?**

집힌다 → 컷을 만든다. **한 단어여도, 말끝이 흐려도 만든다.**
  "오픈시간" → 영업시간을 알린다.  "소금빵" → 소금빵을 알린다.
  "음.. 우리 가게 오픈시간" → 같다. 말끝이 흐릴 뿐 대상은 분명하다.
  그 값이 위 [가게] 정보에 적혀 있으면 그대로 쓴다. 되묻지 않는다 —
  되물으면 사장님은 같은 말을 한 번 더 쓰게 될 뿐이다.

안 집힌다 → {{"cuts": [], "meme_used": null}}
  · 인사("안녕하세요"), "몰라"
  · **광고를 만들어 달라는 말 자체** — "스토리 하나 만들자", "광고 만들어줘", "추천해줘".
    무엇을 알릴지가 빠져 있다. 여기서 소재를 골라 주면 사장님이 정한 적 없는 광고가 된다.
  · **사장님이 되레 묻는 말** — "뭐 만들까?", "어떻게 해?"

규칙 1은 그대로다. 대상이 집혀도 없는 사실은 지어내지 않는다 — 적혀 있는 값으로만 만든다.
"""

_MEME_RULE_SELECTED = (
    "7. 아래 [참고 밈]을 스토리에 자연스럽게 녹인다 — 말투나 분위기를 빌려 오되, "
    "강제로 우겨넣어 어색해지면 안 된다. meme_used엔 그 밈의 id를 그대로 적는다."
)


def _meme_prompt_parts(trend_meme: dict | None) -> tuple[str, str]:
    """(meme_rule, meme_block) — meme_rule은 시스템 프롬프트에, meme_block은 사용자 메시지에 넣는다.
    trend_meme이 없으면 둘 다 빈 문자열이다 — 프롬프트에 밈 얘기 자체가 안 들어간다."""
    if not trend_meme:
        return "", ""
    # meme_recommend.py와 같은 기준 — 이미 하나로 정해진 밈이라 자르지 않고 그대로 넘긴다.
    block = (
        f"[참고 밈: {trend_meme.get('name', '')}]\n"
        f"유래: {trend_meme.get('origin') or ''}\n"
        f"활용예시: {trend_meme.get('usage_example') or ''}\n\n"
    )
    return _MEME_RULE_SELECTED, block

# 사장님이 말한 적 없는 숫자를 잡는다. 프롬프트로 "지어내지 마라"를 적어도 모델은
# "단돈 3,000원!" 같은 문장을 만든다 — 그건 가게에 실제로 없는 가격이다.
# 프롬프트는 부탁이고 여기가 보장이다(sheet_llm 과 같은 태도).
_MONEY_OR_RATE = re.compile(r"(\d[\d,]*)\s*(?:원|%|퍼센트)")


def available() -> bool:
    """LLM을 쓸 수 있는가. 키가 없으면 조용히 규칙 기반으로 돈다."""
    return bool(settings.openai_api_key)


def _ask(system: str, user: str) -> dict | None:
    """LLM에 묻고 JSON을 받는다. 무엇이 잘못되든 None — 대화를 막지 않는다."""
    if not available():
        return None
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
                "temperature": 0.4,
            },
            timeout=settings.openai_timeout_seconds,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else None
    except Exception as exc:  # 네트워크·인증·응답 형식 무엇이든
        # 키를 로그에 흘리지 않는다 — 예외 문자열에 URL은 남아도 헤더는 남지 않는다.
        logger.warning("스토리 LLM 호출 실패, 규칙 기반으로 진행합니다: %s", type(exc).__name__)
        return None


def cut_count(ad_type: str) -> int:
    """광고 종류가 정하는 컷 수. 4컷만화는 네 컷, 인스타 게시물은 한 장짜리 게시물이라 한 컷."""
    return 4 if (ad_type or "").strip() == "4컷만화" else 1


def _context(store: dict, char: dict, ad: dict, prods: list[dict], current_plan: list[dict]) -> str:
    def line(label: str, value) -> str:
        value = (str(value) if value is not None else "").strip()
        return f"{label}: {value}" if value else f"{label}: (비어 있음 — 쓰지 말 것)"

    prod_lines = [
        f"- {p.get('name')} {p.get('qty') or ''} ({p.get('date') or ''} {p.get('time') or ''}"
        + (f", 매진 {p['sold_out']}" if p.get("sold_out") else ", 매진 시각 미입력") + ")"
        for p in prods
    ] or ["- (기록 없음)"]

    parts = [
        "[가게]",
        line("업종", store.get("category")),
        line("주소", store.get("address")),
        line("영업시간", store.get("hours")),
        line("소개", store.get("desc")),
        "",
        "[마스코트]",
        line("이름", char.get("name")),
        line("외형", char.get("look")),
        line("아웃핏", char.get("outfit")),
        line("성격·역할", char.get("desc")),
        "",
        "[광고]",
        line("종류", ad.get("ad_type")),
        line("느낌", ad.get("ad_concept")),
        "",
        "[생산 기록]",
        *prod_lines,
    ]
    if current_plan:
        parts += ["", "[지금까지 정해진 컷 — 참고만 한다]"]
        parts += [f"{c.get('n')}. {c.get('line', '')}" for c in current_plan]
    return "\n".join(parts)


def plan_from_text(
    text: str,
    *,
    store: dict,
    char: dict,
    ad: dict,
    prods: list[dict],
    current_plan: list[dict],
    trend_meme: dict | None = None,
) -> dict | None:
    """사장님 문장 → 컷 구성. 못 쓰면 None, 광고 내용이 아니면 {"cuts": [], "meme_used": None}.

    trend_meme — 트렌드 화면에서 미리 골라 온 밈({id,name,origin,usage_example}). 없으면
    밈 얘기 자체를 프롬프트에 안 넣는다 — GPT가 스스로 밈을 골라 끼워 넣지 않는다.
    """
    if not available() or not (text or "").strip():
        return None

    n = cut_count(ad.get("ad_type", ""))
    meme_rule, meme_block = _meme_prompt_parts(trend_meme)
    system = _PLAN_SYSTEM.format(cameras=" | ".join(CAMERA_TAGS), n=n, meme_rule=meme_rule)
    user = (
        f"{_context(store, char, ad, prods, current_plan)}\n\n"
        + meme_block +
        f"[사장님이 방금 한 말]\n{text.strip()}"
    )
    parsed = _ask(system, user)
    if parsed is None:
        return None

    raw = parsed.get("cuts")
    if not isinstance(raw, list):
        return None
    if not raw:
        return {"cuts": [], "meme_used": None}  # 모델이 "광고로 만들 내용이 아니다"라고 답한 것

    # 사장님 말 + 가게 정보에 있는 숫자만 허용한다. 숫자 검사의 건초더미다.
    haystack = (text or "") + " " + _context(store, char, ad, prods, current_plan)

    cuts: list[dict] = []
    for i, c in enumerate(raw[:n]):
        if not isinstance(c, dict):
            return None
        cut_line = str(c.get("line") or "").strip()
        action = str(c.get("action") or "").strip()
        if not cut_line or not action:
            return None
        if len(cut_line) > 80 or len(action) > 160:
            # 길면 컷이 아니라 줄거리다. 말풍선에도 들어가지 않는다.
            return None
        if _invents_numbers(cut_line, haystack) or _invents_numbers(action, haystack):
            logger.info("가게에 없는 숫자를 지어내 컷 구성을 버렸습니다")
            return None
        camera = str(c.get("camera") or "").strip()
        cuts.append({
            "n": i + 1,
            "line": cut_line,
            "short": cut_line[:14],
            "action": action,
            "camera": camera if camera in CAMERA_TAGS else "",
            "props": [str(p) for p in (c.get("props") or []) if str(p).strip()],
        })

    # 컷이 하나도 안 왔으면 모델이 형식을 놓친 것으로 본다. 인스타 게시물은 원래
    # 한 컷이 정상이라 여기서 최소 개수를 강제하지 않는다 — n이 몇 개를 요구했는지는
    # 위에서 이미 raw[:n]로 잘라냈다.
    if not cuts:
        return None

    # trend_meme이 있으면 이미 정해진 값을 그대로 쓴다(GPT의 echo를 믿을 필요가 없다).
    # 없으면 애초에 프롬프트에 밈 얘기를 안 넣었으니 meme_used는 항상 None이다.
    meme_used = {"id": trend_meme["id"], "name": trend_meme.get("name", "")} if trend_meme else None

    return {"cuts": cuts, "meme_used": meme_used}


def _invents_numbers(value: str, haystack: str) -> bool:
    """값에 든 금액·비율이 사장님 말이나 가게 정보에 없는 숫자인가."""
    digits = re.sub(r"[^0-9]", "", haystack)
    for match in _MONEY_OR_RATE.finditer(value or ""):
        number = match.group(1).replace(",", "")
        if number not in digits:
            return True
    return False


_CAPTION_SYSTEM = """\
너는 한국 동네 가게 사장님의 인스타그램 게시물 캡션을 써주는 카피라이터다.
사장님이 이미 확정한 광고 컷 내용을 재료로, 인스타에 그대로 올릴 캡션 하나를 쓴다.

규칙:
1. 컷 내용·가게 정보에 없는 사실(가격·할인율·수량·시간)은 지어내지 않는다.
2. 실제 SNS 게시물처럼 쓴다 — 짧은 문장, 줄바꿈, 어울리는 이모지 1~3개, 자연스러운
   마무리(질문·초대 등). 컷 대사를 그대로 나열하지 않는다 — 하나의 글로 자연스럽게 잇는다.
3. 광고 느낌(컨셉)을 말투에 반영한다. 느낌을 설명하는 문장을 쓰지 않는다.
4. 마지막 줄에 해시태그 3~5개(#으로 시작, 공백 없이) — 업종·동네·컷에 나온 품목에서 뽑는다.
5. 전체 300자를 넘기지 않는다.
{meme_rule}

출력은 캡션 텍스트만 — 설명, 따옴표, 마크다운 없이 그대로.
"""


def generate_caption(
    *,
    store: dict,
    char: dict,
    ad: dict,
    prods: list[dict],
    plan: list[dict],
    trend_meme: dict | None = None,
) -> str | None:
    """확정된 컷(plan)으로 인스타 캡션을 새로 쓴다. 컷 대사(line)는 말풍선용이라 40자
    제한이 있어 그대로 이어붙이면 SNS 톤이 안 산다 — 컷 내용을 재료 삼아 이모지·줄바꿈·
    해시태그가 있는 실제 캡션을 따로 만든다.

    실패하면(키 없음·네트워크·형식 이상·가게에 없는 숫자를 지어냄) None — 호출부가
    컷 이어붙이기(옛 방식)로 조용히 돌아간다.
    """
    if not available() or not plan:
        return None

    meme_rule = ""
    meme_block = ""
    if trend_meme:
        meme_rule = "6. [참고 밈]을 캡션 말투나 분위기에 살짝 녹여도 된다 — 억지로 우겨넣지 않는다."
        # meme_recommend.py·_meme_prompt_parts와 같은 기준 — 활용예시도 빠져 있었는데
        # 컷 구성에는 넣으면서 캡션에는 안 넣을 이유가 없어 같이 넣는다. 자르지 않는다.
        meme_block = (
            f"\n[참고 밈: {trend_meme.get('name', '')}]\n"
            f"유래: {trend_meme.get('origin') or ''}\n"
            f"활용예시: {trend_meme.get('usage_example') or ''}\n"
        )

    system = _CAPTION_SYSTEM.format(meme_rule=meme_rule)
    cuts_text = "\n".join(f"{c.get('n')}. {c.get('line', '')}" for c in plan)
    context = _context(store, char, ad, prods, [])
    user = f"{context}\n{meme_block}\n[확정된 컷]\n{cuts_text}"

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
                "temperature": 0.6,
            },
            timeout=settings.openai_timeout_seconds,
        )
        response.raise_for_status()
        caption = (response.json()["choices"][0]["message"]["content"] or "").strip()
    except Exception as exc:
        logger.warning("캡션 생성 실패, 컷 이어붙이기로 진행합니다: %s", type(exc).__name__)
        return None

    if not caption or len(caption) > 500:
        return None
    if _invents_numbers(caption, cuts_text + " " + context):
        logger.info("가게에 없는 숫자를 지어내 캡션을 버렸습니다")
        return None
    return caption
