"""트렌드 확인 화면 — 밈 추천, GPT 호출 한 번.

프롬프트 안에서 두 단계를 시킨다: (1) 후보들의 situation(활용 상황) 중 지금 가게·캐릭터·
오늘 알릴 내용에 가장 맞는 것 하나를 고르고, (2) 그 situation에 속한 후보 안에서 밈을
하나 골라 이유와 함께 낸다. 호출을 나눠서(situation부터 확정하고 그 결과로 두 번째
호출을 보내는 방식) 만들었다가, 순서상 어쩔 수 없이 매번 왕복 두 번이라 느려서 한 번의
호출·한 번의 JSON 응답 안에 두 단계를 다 넣었다. 검증(아래 situation 확인)으로 "정한
situation과 다른 후보를 골랐다" 같은 응답 불일치를 걸러낸다.

한때 두 개를 보여줬다 — 하나만 던지면 "이게 최선인가" 의심이 든다는 이유였는데, 실제로는
situation별 후보 수가 들쭉날쭉해서(하나뿐인 상황도 있다) "어떨 땐 1개, 어떨 땐 2개"가 더
혼란스러웠다. 어떤 situation으로 좁혔는지 화면에 보여주는 것만으로 "왜 이 밈인지" 납득엔
충분하다고 보고 하나로 되돌렸다. `n`은 나중에 다시 여러 개로 바꿀 수 있게 인자로 남겨둔다.

story_llm.py의 밈 반영과는 목적이 다르다 — 여기는 "지금 상황에 맞는 밈 하나를 짧게
추천"하는 트렌드 확인 화면 전용이라 별도 파일로 둔다.

이 파일만 비동기(AsyncOpenAI)로 GPT를 부른다 — 다른 서비스(sheet_llm·story_llm·chat_ai)는
전부 동기 호출이고 FastAPI가 스레드풀에서 돌려 그걸로 충분하다. 여기만 바꾼 이유는 단순히
"요청이 왔다"는 것뿐, 원칙이 있는 건 아니다 — 나중에 트래픽이 늘어 스레드풀이 부족해지면
다른 곳도 같은 방식으로 옮기면 된다. 이 라우트(trend.py의 /recommend)만 async def다.
"""

from __future__ import annotations

import json

from openai import AsyncOpenAI

from app.core.config import settings

_PROMPT_TMPL = (
    "당신은 동네 가게 광고에 쓸 밈을 골라주는 편집자다. 가게 정보, 가게 마스코트 캐릭터 정보, "
    "사장님이 오늘 알리고 싶은 내용(있으면), 밈 후보 목록(각각 어떤 활용 상황(situation)에 속하는지 "
    "표시됨)을 준다. 순서대로 한다: "
    "(1) 후보들의 situation 값 중 지금 상황에 가장 잘 맞는 것 하나를 정한다. "
    "(2) 그 situation에 속한 후보 중에서 가장 잘 어울리는 것부터 정확히 {n}개를 고른다 "
    "(후보가 {n}개보다 적으면 있는 만큼 전부 고른다). "
    "JSON 하나만 출력한다: {{\"situation\": (1)에서 정한 값, "
    "\"picks\": [{{\"meme_id\": 후보 id, \"reason\": 왜 골랐는지 한국어로 1~2문장}}, ...]}}. "
    "situation은 후보들의 situation 값 중 하나여야 한다. meme_id는 그 situation에 속한 후보의 id여야 "
    "하고(다른 situation 후보를 섞지 않는다), 서로 겹치지 않게 고른다. "
    "오늘 알리고 싶은 내용이 있으면 그 내용과 밈의 유래·활용예시가 실제로 어떻게 연결되는지 reason에 "
    "구체적으로 적는다."
)


def _client() -> AsyncOpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY가 비어 있어 추천을 만들 수 없어요")
    # 타임아웃을 안 주면 SDK 기본값(훨씬 길다)에 맡겨져, OpenAI가 느려질 때 nginx의
    # 60초 응답 대기보다 오래 걸려 친절한 에러 대신 그냥 502가 뜬다.
    # 비동기 클라이언트를 쓴다 — 이 흐름에서 오래 걸리는 건 이 호출 하나뿐이라, 기다리는
    # 동안 이벤트 루프가 다른 요청을 처리할 수 있게(FastAPI 라우트도 async def로 받는다).
    return AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)


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

    # 이름·유래·활용예시를 자르지 않고 그대로 넘긴다 — 후보가 25개뿐이라 원문을
    # 통째로 넣어도 토큰 부담이 적다. 잘라서 넘기면 GPT가 정작 중요한 부분을 못 보고
    # 엉뚱한 이유를 댈 수 있다.
    lines = [
        f"- id: {c['id']} / 상황: {c.get('situation') or ''} / 이름: {c['name']} "
        f"/ 유래: {c['origin'] or ''} / 활용예시: {c['usage_example'] or ''}"
        for c in candidates
    ]
    user = (
        f"[가게] {store_desc or '아직 가게 정보를 입력하지 않음'}\n"
        f"[가게 마스코트] {character_desc or '아직 캐릭터를 확정하지 않음'}\n"
        f"[오늘 알리고 싶은 내용] {note or '따로 적지 않음'}\n\n"
        f"[활용 상황 목록]\n" + "\n".join(f"- {s}" for s in situations) + "\n\n"
        "[후보 목록]\n" + "\n".join(lines)
    )
    resp = await _client().chat.completions.create(
        model=settings.openai_model,
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _PROMPT_TMPL.format(n=n)},
            {"role": "user", "content": user},
        ],
    )
    data = json.loads(resp.choices[0].message.content or "{}")

    situation = str(data.get("situation") or "")
    if situation not in situations:
        raise RuntimeError("추천 결과 형식이 어긋났어요 — 다시 시도해 주세요")

    raw = data.get("picks")
    if not isinstance(raw, list) or not raw:
        raise RuntimeError("추천 결과 형식이 어긋났어요 — 다시 시도해 주세요")

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
        raise RuntimeError("추천 결과 형식이 어긋났어요 — 다시 시도해 주세요")
    return {"situation": situation, "picks": picks}
