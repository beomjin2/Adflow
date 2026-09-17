"""트렌드 확인 화면 — 활용 상황(situation) 안에서 밈 하나를 추천한다. GPT 호출 한 번.

meme_ai.py(밈 카드·네컷 스토리)와는 다루는 테이블이 다르다(MemeCard가 아니라 크롤링
트렌드 Meme) — 화면 목적도 "카테고리 안에서 오늘 이걸 쓰면 좋은 이유"를 짧게 받는
정도라 별도 파일로 둔다.
"""

from __future__ import annotations

import json

from openai import OpenAI

from app.core.config import settings

_PROMPT = (
    "당신은 동네 가게 광고에 쓸 밈을 골라주는 편집자다. 같은 활용 상황(situation) 카테고리에 속한 "
    "밈 후보 목록과 가게 마스코트 캐릭터 정보, 사장님이 오늘 알리고 싶은 내용(있으면)을 보고 "
    "후보 중 가장 잘 어울리는 밈 하나를 고른다. "
    "JSON 하나만 출력한다: {\"meme_id\": 후보 목록에 있는 id 중 하나, "
    "\"reason\": 왜 골랐는지 한국어로 1~2문장}. "
    "meme_id는 반드시 후보 목록에 있는 값 그대로여야 하고, 없는 값을 지어내지 않는다. "
    "오늘 알리고 싶은 내용이 있으면 그 내용과 밈의 유래·활용예시가 실제로 어떻게 연결되는지 reason에 구체적으로 적는다."
)


def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY가 비어 있어 추천을 만들 수 없어요")
    return OpenAI(api_key=settings.openai_api_key)


def recommend_meme(situation: str, note: str, character_desc: str, candidates: list[dict]) -> dict:
    """candidates: [{"id", "name", "origin", "usage_example"}, ...] (같은 situation인 것만 넘긴다).
    반환: {"meme_id", "reason"}. meme_id가 candidates에 없거나 reason이 비면 RuntimeError."""
    lines = [
        f"- id: {c['id']} / 이름: {c['name']} / 유래: {(c['origin'] or '')[:120]} "
        f"/ 활용예시: {(c['usage_example'] or '')[:120]}"
        for c in candidates
    ]
    user = (
        f"[활용 상황] {situation}\n"
        f"[가게 마스코트] {character_desc or '아직 캐릭터를 확정하지 않음'}\n"
        f"[오늘 알리고 싶은 내용] {note or '따로 적지 않음'}\n\n"
        "[후보 목록]\n" + "\n".join(lines)
    )
    resp = _client().chat.completions.create(
        model=settings.openai_model,
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": _PROMPT}, {"role": "user", "content": user}],
    )
    data = json.loads(resp.choices[0].message.content or "{}")
    meme_id = str(data.get("meme_id") or "")
    reason = str(data.get("reason") or "").strip()
    valid_ids = {c["id"] for c in candidates}
    if meme_id not in valid_ids or not reason:
        raise RuntimeError("추천 결과 형식이 어긋났어요 — 다시 시도해 주세요")
    return {"meme_id": meme_id, "reason": reason}
