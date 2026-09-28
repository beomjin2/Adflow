"""밈 추천 — GPT 호출 방식이 화면마다 다르다.

`recommend()` — 스토리보드(광고 만들기) 화면의 "밈 추천받기"용. situation(활용 상황) 고르기와
밈 n개 고르기를 한 호출·한 JSON 응답 안에 같이 시킨다. 원래 두 호출로 나눴다가 왕복이 두 번이라
느려서 합친 것 — 지금도 이 화면은 그 판단 그대로다.

`recommend_split()` — 트렌드 확인 화면의 "추천" 버튼용. 같은 두 단계를 **호출 두 번**으로 나눈다
(2026-09-22 사용자 결정 — 스토리보드 쪽은 그대로 두고 이 화면만 되돌림). (1) situation 이름
목록만 보고 하나를 고르는 호출, (2) 그 situation으로 이미 좁힌 후보 안에서 밈 n개를 고르는
호출. 왕복이 늘어나는 대신, 밈이 수백~1000개로 늘어도 각 호출이 보는 후보 수는 항상
situation 하나 분량으로 묶여 있다 — 전체 후보를 한 번에 다 보여주지 않는다.

story_llm.py의 밈 반영과는 목적이 다르다 — 여기는 "지금 상황에 맞는 밈 몇 개를 짧게
추천"하는 전용 서비스라 별도 파일로 둔다.

이 파일만 비동기(AsyncOpenAI)로 GPT를 부른다 — 다른 서비스(sheet_llm·story_llm·chat_ai)는
전부 동기 호출이고 FastAPI가 스레드풀에서 돌려 그걸로 충분하다. 여기만 바꾼 이유는 단순히
"요청이 왔다"는 것뿐, 원칙이 있는 건 아니다 — 나중에 트래픽이 늘어 스레드풀이 부족해지면
다른 곳도 같은 방식으로 옮기면 된다. 두 라우트(trend.py의 /recommend, storyboard.py의
/recommend-meme) 다 async def다.
"""

from __future__ import annotations

import json
import random

from openai import AsyncOpenAI, AuthenticationError

from app.core.config import settings

_PROMPT_TMPL = (
    "당신은 동네 가게 광고에 쓸 밈을 골라주는 편집자다. 가게 정보, 가게 마스코트 캐릭터 정보, "
    "사장님이 오늘 알리고 싶은 내용(있으면), 밈 후보 목록(각각 어떤 활용 상황(situation)에 속하는지 "
    "표시됨)을 준다. 순서대로 한다: "
    "(1) '오늘 알리고 싶은 내용'이 있으면 그것을 최우선 신호로 삼아 후보들의 situation 값 중 지금 "
    "상황에 가장 잘 맞는 것 하나를 정한다(가게·캐릭터 정보는 보충 배경일 뿐 이보다 우선하지 않는다). "
    "그 내용이 없으면 가게·캐릭터 정보 전체 분위기로 정한다. "
    "(2) 그 situation에 속한 후보 중에서 가장 잘 어울리는 것부터 정확히 {n}개를 고른다 "
    "(후보가 {n}개보다 적으면 있는 만큼 전부 고른다). "
    "JSON 하나만 출력한다: {{\"situation\": (1)에서 정한 값, "
    "\"picks\": [{{\"meme_id\": 후보 id, \"reason\": 왜 골랐는지 한국어로 3~4문장, 합쳐서 "
    "200자 안팎으로}}, ...]}}. "
    "situation은 후보들의 situation 값 중 하나여야 한다. meme_id는 그 situation에 속한 후보의 id여야 "
    "하고(다른 situation 후보를 섞지 않는다), 서로 겹치지 않게 고른다. "
    "reason 작성 규칙: 3~4문장·200자 안팎으로 쓰되, 여러 근거를 그냥 나열하지 말고 하나의 자연스러운 "
    "글처럼 앞뒤가 맞게 이어 쓴다 — 이 밈의 유래·활용예시가 지금 situation과 왜 맞는지, 그리고 "
    "(가게·캐릭터 정보가 있으면) 그 정보와는 또 어떻게 통하는지, 인과관계가 드러나도록 한 흐름으로 "
    "설명한다. 그 안에 유래·활용예시 원문의 실제 표현을 한 번은 구체적으로 짚어서 근거를 댄다. "
    "가게·캐릭터 정보가 아직 없으면 그 부분은 그냥 생략한다 — 없는 정보를 지어내지 않는다. 오늘 "
    "알리고 싶은 내용이 있으면 그 내용과 어떻게 연결되는지도 자연스럽게 엮는다. '분위기가 잘 "
    "어울려서'처럼 근거 없이 뭉뚱그리지 않고, ①②③ 같은 번호나 여러 문단으로 쪼개지 않는다."
)

# ---------- recommend_split() 전용 프롬프트 (호출 두 번으로 나눈 버전) ----------

# crawling/classify_memes_situation.py의 situation_categories에 있는 "설명"을 그대로
# 옮겨왔다 — DB엔 분류 결과(situation 이름)만 남고 이 설명 문단은 저장되지 않아서,
# 백엔드가 스스로는 알 방법이 없다. 크롤링 쪽 예시문장/설명을 고치면 여기도 같이
# 고쳐야 한다(자동 동기화 없음, 2026-09-22 사용자 결정으로 일단 복사해 넣음).
# "미분류"는 그 스크립트의 카테고리 목록에 없는 특수값(유사도가 임계값 미만일 때
# 붙는 이름)이라 설명이 없다 — situations 목록엔 나올 수 있고, 그때는 이름만 보여준다.
_SITUATION_DESCRIPTIONS = {
    "반응_기다림": "상대방의 답장, 연락, 반응 또는 결과를 기다리는 상황. 답이 오지 않거나 결과를 "
                  "기다리면서 궁금해하거나 초조해하거나 투정하는 상황이 핵심이다.",
    "전후_비교": "어떤 행동이나 사건을 기준으로 이전과 이후의 상태가 달라지는 모습을 비교해서 "
                "보여주는 상황. 비포와 애프터처럼 변화 전후를 대비하는 것이 핵심이다.",
    "신규_시작": "새로운 제품, 서비스, 활동 또는 도전을 처음 시작하거나 출시하는 상황. 새로운 것을 "
                "시작한다는 의미가 핵심이다.",
    "감탄_긍정반응": "사람, 제품, 음식, 결과 또는 상황이 마음에 들거나 좋아서 감탄하거나 칭찬하거나 "
                    "긍정적인 반응을 표현하는 상황. 좋다, 최고다, 마음에 든다 등의 긍정적인 반응이 "
                    "핵심이다. 단순히 재미있는 말장난이나 패러디, 챌린지는 포함하지 않는다.",
    "재미_밈놀이": "특정 단어, 숫자, 문장, 소리, 행동 등을 다른 대상에 붙이거나 변형하거나 반복해서 "
                  "재미를 만드는 상황. 언어유희, 말장난, 패러디, 드립, 챌린지, 따라 하기, 참여형 놀이 "
                  "등을 포함한다. 상대방을 일부러 킹받게 하거나 놀리는 장난도 포함한다. 실제로 "
                  "불편함이나 부당함에 대해 불만을 표현하는 것이 목적이라면 포함하지 않는다.",
    "불만_토로": "실제로 겪은 불편함, 답답함, 힘든 상황, 부당함 등에 대해 자신의 불만을 표현하거나 "
                "하소연하거나 투정하는 상황. 단순히 재미를 위해 '킹받게 한다', '열받게 한다'고 "
                "표현하거나 상대방을 놀리는 드립은 포함하지 않는다.",
}


def _situation_lines(situations: list[str]) -> list[str]:
    """situation 이름에 설명이 있으면 같이 붙인다. 없으면(예: "미분류") 이름만 보여준다."""
    out = []
    for s in situations:
        desc = _SITUATION_DESCRIPTIONS.get(s)
        out.append(f"- {s}: {desc}" if desc else f"- {s}")
    return out


_SITUATION_PROMPT = (
    "당신은 동네 가게 광고에 쓸 밈을 추천하는 편집자다. 가게 정보, 가게 마스코트 캐릭터 정보, "
    "밈이 분류된 활용 상황(situation) 목록(이름과 설명)을 준다. 가게·캐릭터 정보 전체의 분위기로 "
    "판단해서, 목록에 적힌 situation 설명과 실제로 맞는 것을 정확히 하나 고른다 — 설명에 없는 "
    "근거로 끼워 맞추지 않는다. "
    "JSON 하나만 출력한다: {\"situation\": 목록 중 고른 이름}."
)

_PICK_PROMPT_TMPL = (
    "당신은 동네 가게 광고에 쓸 밈을 골라주는 편집자다. 가게 정보, 가게 마스코트 캐릭터 정보, "
    "그리고 이미 하나로 정해진 활용 상황(situation) 안의 밈 후보 목록(각 후보의 유래·활용예시 "
    "원문 포함)을 준다. 그중에서 가장 잘 어울리는 것부터 정확히 {n}개를 고른다(후보가 {n}개보다 "
    "적으면 있는 만큼 전부 고른다). "
    "JSON 하나만 출력한다: {{\"picks\": [{{\"meme_id\": 후보 id, "
    "\"situation_reason\": 이 밈이 지금 situation과 왜 맞는지 한국어 1~2문장, 합쳐서 100자 안팎, "
    "\"store_reason\": 가게 업종·캐릭터 성격 등 구체적인 정보가 주어졌을 때만 그 정보와 이 밈이 "
    "어떻게 연결되는지 한국어 1문장, 60자 안팎(가게·캐릭터 정보가 아직 없으면 빈 문자열 \"\"), "
    "\"origin_summary\": 그 후보의 유래 원문을 20자 안팎 한국어 한 문장으로 요약, "
    "\"usage_summary\": 그 후보의 활용예시 원문을 20자 안팎 한국어 한 문장으로 요약}}, ...]}}. "
    "meme_id는 반드시 후보 목록에 있는 id여야 하고, 서로 겹치지 않게 고른다. "
    "situation_reason 작성 규칙: 길게 늘어놓지 않는다(1~2문장·100자 안팎). 그 안에 유래·활용예시 "
    "원문의 실제 표현을 한 번은 구체적으로 짚어서 근거를 댄다 — '분위기가 잘 어울려서'처럼 근거 "
    "없이 뭉뚱그리지 않는다. store_reason은 situation_reason과 내용을 겹치지 않게, 가게·캐릭터 "
    "정보만의 연결점을 새로 짚는다 — 정보가 없으면 절대 지어내지 않고 빈 문자열로 둔다. 둘 다 "
    "①②③ 같은 번호를 쓰지 않고 자연스러운 문장으로 쓴다. "
    "origin_summary·usage_summary는 그 후보의 유래·활용예시 원문에 있는 내용만 "
    "요약한다 — 원문에 없는 내용을 지어내지 않는다."
)

_NARROW_TARGET = 10

_NARROW_PROMPT_TMPL = (
    "당신은 동네 가게 광고에 쓸 밈을 추천하는 편집자다. 가게 정보, 가게 마스코트 캐릭터 정보, "
    "그리고 이미 하나로 정해진 활용 상황(situation) 안의 밈 후보 목록(이름과 유래 일부만 요약해서 "
    "보여줌 — 후보가 너무 많아서 원문 전체는 다음 단계에서 본다)을 준다. 가게·캐릭터 정보와 어울릴 "
    "것 같은 후보부터 최대 {k}개의 id를 고른다(후보가 {k}개보다 적으면 있는 만큼 전부 고른다). "
    "JSON 하나만 출력한다: {{\"ids\": [후보 id, ...]}}. id는 반드시 후보 목록에 있는 값이어야 한다."
)


def _narrow_lines(candidates: list[dict]) -> list[str]:
    # 이 단계는 원문 전체가 아니라 이름과 유래 요약만 보여준다 — 후보가 많을 때 이 목록
    # 자체가 너무 커지는 걸 막기 위해서다. 최종 선택(_candidate_lines)에서는 그대로 원문
    # 전체를 본다.
    #
    # origin_brief — backfill_origin_brief.py가 GPT로 미리 만들어 둔 30자 안팎 요약
    # (models.Meme.origin_brief). 아직 안 채워진 밈(새로 크롤링됐거나 스크립트를 아직 안
    # 돌린 경우)은 빈 문자열이라, 그때만 예전처럼 원문을 60자로 기계적으로 잘라 대신한다 —
    # 요약이 없다고 이 단계 자체가 막히면 안 되니 항상 값이 있게 한다.
    return [
        f"- id: {c['id']} / 이름: {c['name']} / 유래: "
        f"{c.get('origin_brief') or _truncate(c.get('origin') or '', 60)}"
        for c in candidates
    ]


def _candidate_lines(candidates: list[dict]) -> list[str]:
    return [
        f"- id: {c['id']} / 상황: {c.get('situation') or ''} / 이름: {c['name']} "
        f"/ 유래: {c['origin'] or ''} / 활용예시: {c['usage_example'] or ''}"
        for c in candidates
    ]


def _truncate(text: str, limit: int = 24) -> str:
    """GPT가 origin_summary·usage_summary를 안 채웠을 때 쓰는 기계적 대체값. 문장을
    새로 짓지 않고 원문 앞부분만 자른다 — 없는 것보단 낫다는 최후의 보루다."""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _client() -> AsyncOpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY가 비어 있어 추천을 만들 수 없어요")
    # 타임아웃을 안 주면 SDK 기본값(훨씬 길다)에 맡겨져, OpenAI가 느려질 때 nginx의
    # 60초 응답 대기보다 오래 걸려 친절한 에러 대신 그냥 502가 뜬다.
    # 비동기 클라이언트를 쓴다 — 이 흐름에서 오래 걸리는 건 이 호출 하나뿐이라, 기다리는
    # 동안 이벤트 루프가 다른 요청을 처리할 수 있게(FastAPI 라우트도 async def로 받는다).
    return AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)


_MAX_ATTEMPTS = 3


async def _retry(build):
    """build(): 인자 없는 async 함수. GPT를 부르고 파싱·검증까지 한 뒤 결과를 돌려준다.
    형식이 어긋났을 때(파싱 실패·목록에 없는 값 등) build가 예외를 던지면, 그걸 "재시도해도
    되는 실패"로 보고 최대 _MAX_ATTEMPTS번까지 GPT를 다시 부른다. 전부 실패하면 마지막
    예외를 그대로 올린다 — 호출부가 이걸 잡아 사용자에게 보여줄 RuntimeError로 바꾼다.

    RuntimeError·AuthenticationError는 재시도하지 않고 곧장 올린다 — 재시도해도 결과가
    안 바뀌는 실패라서다(RuntimeError는 _client()가 "API 키가 비어 있다"처럼 우리가 이미
    사람이 읽을 문장으로 만들어 둔 에러, AuthenticationError는 키 자체가 잘못된 경우).
    이걸 그냥 재시도하면 3배 느리게 똑같이 실패할 뿐이고, 밑에서 일반 메시지로 덮어써서
    "API 키가 비어 있어요" 같은 정확한 원인이 사라진다(2026-09-28 확인 — 실제로 이 버그
    때문에 400 에러 메시지가 "형식이 어긋났어요"로만 떠서 원인을 알 수 없었다)."""
    last: Exception = RuntimeError("추천 결과 형식이 어긋났어요")
    for _ in range(_MAX_ATTEMPTS):
        try:
            return await build()
        except (RuntimeError, AuthenticationError):
            raise
        except Exception as e:  # noqa: BLE001 — GPT 응답 파싱·검증 실패는 전부 재시도 대상
            last = e
    raise last


async def recommend(note: str, character_desc: str, store_desc: str, candidates: list[dict],
                    n: int = 1, exclude: set[str] | None = None) -> dict:
    """candidates: [{"id","name","situation","origin","usage_example"}, ...] — situation별로
    미리 좁히지 않은 전체 후보. "미분류"도 정상적인 situation 중 하나로 그대로 들어온다.
    반환: {"situation": str, "picks": [{"meme_id","reason"}, ...]} (picks 1~n개).
    situation이 후보 목록에 없거나, 유효한 pick이 하나도 안 남으면 RuntimeError.

    exclude — 이미 보여준 밈의 id. **후보에서 미리 빼고 GPT에 넘긴다.**
    프롬프트로 "빼 달라"고 부탁하는 것과 다르다 — 목록에 없으면 고를 수가 없다.
    빼고 나서 아무것도 안 남으면 뺀 걸 되살린다. 추천이 아예 안 나오는 것보다는
    같은 게 다시 나오는 편이 낫다."""
    pool = candidates
    if exclude:
        trimmed = [c for c in candidates if c["id"] not in exclude]
        if trimmed:
            pool = trimmed
    candidates = pool

    situations = sorted({c["situation"] for c in candidates if c.get("situation")})
    if not situations:
        raise RuntimeError("분류된 밈이 없어요")

    lines = _candidate_lines(candidates)
    user = (
        f"[가게] {store_desc or '아직 가게 정보를 입력하지 않음'}\n"
        f"[가게 마스코트] {character_desc or '아직 캐릭터를 확정하지 않음'}\n"
        f"[오늘 알리고 싶은 내용] {note or '따로 적지 않음'}\n\n"
        f"[활용 상황 목록]\n" + "\n".join(f"- {s}" for s in situations) + "\n\n"
        "[후보 목록]\n" + "\n".join(lines)
    )

    async def _call():
        resp = await _client().chat.completions.create(
            model=settings.openai_meme_model,
            # gpt-5-mini는 temperature 커스텀 값을 못 받는다(기본값 1만 허용) — 뺀다.
            # reasoning_effort="minimal" — 이 정도 분류·선택 작업엔 깊은 추론이 필요 없는데
            # 기본 추론 강도로는 응답이 10초 넘게 걸려서(2026-09-28 실측) 낮춘다.
            reasoning_effort="minimal",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _PROMPT_TMPL.format(n=n)},
                {"role": "user", "content": user},
            ],
        )
        data = json.loads(resp.choices[0].message.content or "{}")

        situation = str(data.get("situation") or "")
        if situation not in situations:
            raise ValueError("situation not in list")

        raw = data.get("picks")
        if not isinstance(raw, list) or not raw:
            raise ValueError("no picks")

        by_id = {c["id"]: c for c in candidates}
        seen: set[str] = set()
        picks: list[dict] = []
        for p in raw[:n]:
            meme_id = str((p or {}).get("meme_id") or "")
            reason = str((p or {}).get("reason") or "").strip()
            cand = by_id.get(meme_id)
            # 정한 situation과 다른 situation의 후보를 섞어 냈으면(모델이 지시를 안 따른 경우)
            # 그 항목만 버린다 — 나머지가 유효하면 그대로 쓴다.
            if not cand or not reason or meme_id in seen or cand.get("situation") != situation:
                continue
            seen.add(meme_id)
            picks.append({"meme_id": meme_id, "reason": reason})

        if not picks:
            raise ValueError("no valid picks")
        return {"situation": situation, "picks": picks}

    try:
        return await _retry(_call)
    except (RuntimeError, AuthenticationError):
        raise  # _client()의 "API 키가 비어 있다" 같은 원래 메시지를 그대로 살린다.
    except Exception:
        raise RuntimeError("추천 결과 형식이 어긋났어요 — 다시 시도해 주세요")


async def recommend_split(character_desc: str, store_desc: str, candidates: list[dict],
                           n: int = 3, exclude: set[str] | None = None,
                           exclude_situations: set[str] | None = None) -> dict:
    pool = candidates
    if exclude:
        trimmed = [c for c in candidates if c["id"] not in exclude]
        if trimmed:
            pool = trimmed
    candidates = pool

    situations = sorted({c["situation"] for c in candidates if c.get("situation")})
    if not situations:
        raise RuntimeError("분류된 밈이 없어요")

    available_situations = situations
    if exclude_situations:
        trimmed_situations = [s for s in situations if s not in exclude_situations]
        if trimmed_situations:
            available_situations = trimmed_situations

    if len(available_situations) > 1:
        keep_n = random.randint(1, min(3, len(available_situations)))
        available_situations = random.sample(available_situations, keep_n)

    client = _client()

    # ---- 호출 1: situation 고르기 (밈 후보 상세는 안 보여준다) ----
    situation_user = (
        f"[가게] {store_desc or '아직 가게 정보를 입력하지 않음'}\n"
        f"[가게 마스코트] {character_desc or '아직 캐릭터를 확정하지 않음'}\n\n"
        f"[활용 상황 목록]\n" + "\n".join(_situation_lines(available_situations))
    )
    async def _call1():
        resp1 = await client.chat.completions.create(
            model=settings.openai_meme_model,
            reasoning_effort="minimal",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SITUATION_PROMPT},
                {"role": "user", "content": situation_user},
            ],
        )
        s = str((json.loads(resp1.choices[0].message.content or "{}") or {}).get("situation") or "")
        if s not in available_situations:
            raise ValueError("situation not in list")
        return s

    try:
        situation = await _retry(_call1)
    except (RuntimeError, AuthenticationError):
        raise  # _client()의 "API 키가 비어 있다" 같은 원래 메시지를 그대로 살린다.
    except Exception:
        raise RuntimeError("추천 결과 형식이 어긋났어요 — 다시 시도해 주세요")

    # ---- 호출 2: 그 situation 안에서만 밈 n개 고르기 ----
    narrowed = [c for c in candidates if c.get("situation") == situation]

    if len(narrowed) > _NARROW_TARGET:
        narrow_by_id = {c["id"]: c for c in narrowed}
        narrow_lines_text = "\n".join(_narrow_lines(narrowed))

        async def _call_narrow():
            resp0 = await client.chat.completions.create(
                model=settings.openai_meme_model,
                reasoning_effort="minimal",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _NARROW_PROMPT_TMPL.format(k=_NARROW_TARGET)},
                    {"role": "user", "content": (
                        f"[가게] {store_desc or '아직 가게 정보를 입력하지 않음'}\n"
                        f"[가게 마스코트] {character_desc or '아직 캐릭터를 확정하지 않음'}\n"
                        f"[정해진 활용 상황] {situation}\n\n"
                        f"[후보 목록]\n{narrow_lines_text}"
                    )},
                ],
            )
            ids = (json.loads(resp0.choices[0].message.content or "{}") or {}).get("ids")
            if not isinstance(ids, list) or not ids:
                raise ValueError("no narrowed ids")
            picked = [narrow_by_id[i] for i in ids if i in narrow_by_id][:_NARROW_TARGET]
            if not picked:
                raise ValueError("no valid narrowed ids")
            return picked

        try:
            narrowed = await _retry(_call_narrow)
        except Exception:
            narrowed = random.sample(narrowed, _NARROW_TARGET)

    pick_user = (
        f"[가게] {store_desc or '아직 가게 정보를 입력하지 않음'}\n"
        f"[가게 마스코트] {character_desc or '아직 캐릭터를 확정하지 않음'}\n"
        f"[정해진 활용 상황] {situation}\n\n"
        "[후보 목록]\n" + "\n".join(_candidate_lines(narrowed))
    )
    async def _call2():
        resp2 = await client.chat.completions.create(
            model=settings.openai_meme_model,
            # gpt-5-mini는 temperature 커스텀 값을 못 받는다(기본값 1만 허용) — 뺀다.
            reasoning_effort="minimal",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _PICK_PROMPT_TMPL.format(n=n)},
                {"role": "user", "content": pick_user},
            ],
        )
        raw = (json.loads(resp2.choices[0].message.content or "{}") or {}).get("picks")
        if not isinstance(raw, list) or not raw:
            raise ValueError("no picks")

        by_id = {c["id"]: c for c in narrowed}
        seen: set[str] = set()
        result: list[dict] = []
        for p in raw[:n]:
            meme_id = str((p or {}).get("meme_id") or "")
            # situation_reason·store_reason — 화면이 "상황 근거"와 "가게·캐릭터 연결"을 별도
            # 항목으로 나눠 보여주기 위해 둘로 쪼갰다(2026-09-28 사용자 결정 — 한 문단에
            # 섞여 있으면 어디까지가 상황 근거고 어디부터가 가게 얘기인지 구분이 안 됐다).
            # situation_reason은 항상 있어야 하는 필수값이고, store_reason은 가게·캐릭터
            # 정보가 없으면 GPT가 빈 문자열을 낸다 — 그럴 땐 화면이 그 줄을 그냥 안 그린다.
            situation_reason = str((p or {}).get("situation_reason") or "").strip()
            store_reason = str((p or {}).get("store_reason") or "").strip()
            cand = by_id.get(meme_id)
            # 호출 2의 후보 자체가 이미 situation으로 좁혀져 있어서, id가 맞으면
            # situation도 자동으로 맞다 — 그래도 존재하지 않는 id(환각)는 걸러낸다.
            if not cand or not situation_reason or meme_id in seen:
                continue
            seen.add(meme_id)
            result.append({
                "meme_id": meme_id,
                "situation_reason": situation_reason,
                "store_reason": store_reason,
                "origin_summary": str((p or {}).get("origin_summary") or "").strip()
                or _truncate(cand.get("origin") or ""),
                "usage_summary": str((p or {}).get("usage_summary") or "").strip()
                or _truncate(cand.get("usage_example") or ""),
            })

        if not result:
            raise ValueError("no valid picks")
        return result

    try:
        picks = await _retry(_call2)
    except (RuntimeError, AuthenticationError):
        raise  # _client()의 "API 키가 비어 있다" 같은 원래 메시지를 그대로 살린다.
    except Exception:
        raise RuntimeError("추천 결과 형식이 어긋났어요 — 다시 시도해 주세요")
    return {
        "situation": situation,
        "picks": picks,
        "situation_description": _SITUATION_DESCRIPTIONS.get(situation, ""),
        "situation_candidate_count": len(narrowed),
    }
