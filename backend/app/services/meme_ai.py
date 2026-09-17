"""밈 → 카드 → 네컷 스토리. GPT 호출 두 가지.

배경 담당의 실험 기록(2026-09-16)을 앱으로 옮긴 것이다:
  밈 원문 → (1) 밈 카드: 정의·유행 이유·말 틀·시각 요소·업종·피할 것   — 밈당 한 번, 저장
  카드 + 가게 정보 → (2) 네컷 스토리: 컷별 대사·동작·카메라·소품          — 광고마다
그림 프롬프트는 여기서 만들지 않는다. 동작 문장을 danbooru_tags(kind="scene")가 실존
태그로 바꾸고, 캐릭터는 참조 이미지가 잡는다(storyboard 라우트 참고).

실험에서 확인된 규칙 두 가지를 그대로 넣었다: 말 틀을 네 컷 중 세 컷 이상에서 실제로 쓴다
(한 컷에만 있으면 밈이 흐릿해진다), 대시보드 요약이 아니라 원문을 넣어야 카드가 나온다.
"""

from __future__ import annotations

import json
import logging

from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

CARD_KEYS = ("definition", "why", "template", "visual", "industries", "avoid", "understanding")

# 그림 모델이 알아듣는 구도 태그만 허용한다. 자연어 카메라 지시("입구 클로즈업")는 여기로 매핑된다.
CAMERA_TAGS = ("straight-on", "close-up", "from_side", "from_below", "from_above", "wide_shot")

_CARD_PROMPT = (
    "당신은 한국 SNS 밈을 광고 기획자에게 설명하는 편집자다. 아래 밈 원문(뉴스레터 본문 등)을 읽고 "
    "JSON 하나만 출력한다. 키: definition(한 줄 정의), why(유행 이유), template(말 틀 — 대괄호 자리표시로), "
    "visual(그림으로 옮길 때의 시각 요소), industries(어울리는 업종 배열), avoid(피할 것 배열), "
    "understanding(원문만으로 이 밈을 얼마나 확실히 이해했는지 0~1 숫자). "
    "원문에 없는 사실은 지어내지 않는다. 원문이 인사말·잡담뿐이면 understanding을 낮게 주고 definition에 "
    "'원문에서 밈을 특정할 수 없음'이라고 적는다."
)

_STORY_PROMPT = (
    "당신은 동네 빵집의 SNS 네컷 만화를 기획한다. 주어진 밈 카드와 가게 정보로 4컷 스토리를 JSON 하나로 출력한다. "
    "형식: {\"title\": str, \"cuts\": [{\"n\": 1, \"line\": 대사(한국어, 말풍선에 들어갈 짧은 한 문장), "
    "\"action\": 동작(마스코트가 하는 행동·표정·소품·장소를 한국어 한 문장으로, 대사와 글자는 넣지 말 것), "
    "\"camera\": 다음 중 하나 " + " | ".join(CAMERA_TAGS) + ", \"props\": 소품 단어 배열}, ... 4개]}. "
    "규칙: (1) 밈의 말 틀을 네 컷 중 세 컷 이상의 대사에서 실제로 쓴다. (2) 마지막 컷은 가게 이름·영업시간 같은 "
    "실제 정보로 끝낸다. (3) 가게 정보에 있는 수치(예: 매진까지 걸린 시간)를 반전 컷에 쓴다. (4) 카드의 '피할 것'을 "
    "어기지 않는다. (5) 주인공은 가게 마스코트 한 마리이며 사람 손님은 그리지 않는다 — 손님이 필요하면 동물 손님으로 적는다. "
    "(6) 가게 정보에 없는 사실(가격·할인)은 지어내지 않는다."
)


def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY가 비어 있어 밈 카드·스토리를 만들 수 없어요")
    return OpenAI(api_key=settings.openai_api_key)


def _json_chat(system: str, user: str, temperature: float) -> dict:
    resp = _client().chat.completions.create(
        model=settings.openai_model,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    raw = resp.choices[0].message.content or "{}"
    return json.loads(raw)


def make_meme_card(title: str, source: str, original: str) -> dict:
    """밈 원문 → 카드. 키가 빠지면 빈 값으로 채워 형식을 보장한다."""
    data = _json_chat(_CARD_PROMPT, f"밈 이름: {title}\n출처: {source}\n\n원문:\n{original}", temperature=0.2)
    card = {k: data.get(k) for k in CARD_KEYS}
    card["industries"] = list(card.get("industries") or [])
    card["avoid"] = list(card.get("avoid") or [])
    try:
        card["understanding"] = float(card.get("understanding") or 0)
    except (TypeError, ValueError):
        card["understanding"] = 0.0
    for k in ("definition", "why", "template", "visual"):
        card[k] = str(card.get(k) or "")
    return card


def propose_story(card: dict, meme_title: str, store: dict, prods: list[dict], ad: dict, mascot: str) -> dict:
    """카드 + 가게 정보 → {title, cuts[4]}. 컷은 n/line/action/camera/props를 갖는다."""
    prod_lines = [
        f"- {p.get('name')} {p.get('qty') or ''} ({p.get('date') or ''} {p.get('time') or ''}"
        + (f", 매진 {p['sold_out']}" if p.get("sold_out") else "") + ")"
        for p in prods
    ] or ["- (기록 없음)"]
    user = (
        f"[밈 카드: {meme_title}]\n{json.dumps(card, ensure_ascii=False, indent=1)}\n\n"
        f"[가게]\n업종: {store.get('category') or '빵집'}\n주소: {store.get('address') or ''}\n"
        f"영업시간: {store.get('hours') or ''}\n소개: {store.get('desc') or ''}\n"
        f"[생산 기록]\n" + "\n".join(prod_lines) + "\n\n"
        f"[광고] 종류: {ad.get('ad_type') or ''} / 컨셉: {ad.get('ad_concept') or ''}\n"
        f"[마스코트] {mascot or '가게 마스코트'}"
    )
    data = _json_chat(_STORY_PROMPT, user, temperature=0.5)
    cuts = []
    for i, c in enumerate(list(data.get("cuts") or [])[:4]):
        camera = str(c.get("camera") or "").strip()
        cuts.append({
            "n": i + 1,
            "line": str(c.get("line") or "").strip(),
            "action": str(c.get("action") or "").strip(),
            "camera": camera if camera in CAMERA_TAGS else "",
            "props": [str(p) for p in (c.get("props") or [])],
            "short": str(c.get("line") or "")[:14],
        })
    if len(cuts) < 2 or any(not c["line"] or not c["action"] for c in cuts):
        raise RuntimeError("스토리 형식이 어긋났어요 — 다시 제안받아 주세요")
    return {"title": str(data.get("title") or meme_title), "cuts": cuts}
