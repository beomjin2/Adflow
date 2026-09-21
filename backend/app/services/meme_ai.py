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

# 컷 층의 닫힌 슬롯 선택지. chat_ai.SHOT_SIZE/ANGLE/COUNT의 키와 같아야 한다.
SHOT_SIZE_CHOICES = ("아주작게", "작게", "보통", "크게", "아주크게")
SHOT_ANGLE_CHOICES = ("정면", "위에서", "아래에서", "옆에서", "뒤에서")
SHOT_COUNT_CHOICES = ("혼자", "여럿")

# 스토리 GPT가 컷마다 **팀장 슬롯 시트의 컷 층**을 직접 채운다. 예전엔 자유 문장(action)을 내고 그걸
# 또 한 번 GPT가 태그로 바꿨다 — 두 번 거치며 두 번 샜다. 슬롯으로 내면 한 번으로 끝나고,
# 특히 shot.size가 컷마다 달라져 "캐릭터가 매 컷 화면을 채우는" 문제가 풀린다.
# 형식·어휘는 규칙 대신 **예시 두 편**으로 가르친다(09-21 실측: 예시가 규칙보다 글자당 3.4배 효과).
_STORY_PROMPT = (
    "당신은 동네 빵집의 SNS 네컷 만화를 기획한다. 주어진 밈 카드와 가게 정보로 4컷 스토리를 JSON 하나로 출력한다.\n"
    "주인공은 가게 마스코트 한 마리다. 사람 손님은 그리지 않는다 — 손님이 필요하면 동물 손님으로 적는다. "
    "가게 정보에 없는 가격·할인은 지어내지 않는다. 밈의 말 틀을 네 컷 중 세 컷 이상의 대사에서 실제로 쓰고, "
    "마지막 컷은 가게 이름·영업시간 같은 실제 정보로 끝낸다.\n\n"
    "컷마다 아래 칸을 채운다. shot의 세 칸은 반드시 주어진 선택지 중 하나만 쓴다.\n"
    "  line        대사 — 말풍선에 들어갈 짧은 한국어 한 문장\n"
    "  action      한 줄 요약 — 사람이 읽는 용도(그림엔 안 씀)\n"
    f"  shot.size   {' | '.join(SHOT_SIZE_CHOICES)}  (캐릭터가 화면에서 얼마나 크게)\n"
    f"  shot.angle  {' | '.join(SHOT_ANGLE_CHOICES)}\n"
    f"  shot.count  {' | '.join(SHOT_COUNT_CHOICES)}\n"
    "  expression  표정 — 짧은 한국어 구 (예: 놀람, 활짝 웃음, 지침)\n"
    "  pose        동작 — 짧은 한국어 구 (예: 쟁반 들기, 손 흔들기, 팔짱)\n"
    "  place       장소 — 한 단어 (예: 가게 안, 주방, 가게 앞)\n"
    "  props       소품 — 단어 배열 (예: [\"빵\", \"쟁반\"])\n"
    "  light       빛 — 한 단어 또는 빈 문자열 (예: 아침 햇살, 밤)\n\n"
    "예시 1 — 밈 '하겠습니다 / 안 하겠습니다', 소금빵 20개 굽고 1시간 만에 매진:\n"
    "{\"title\": \"안 팔겠습니다\", \"cuts\": [\n"
    " {\"n\": 1, \"line\": \"오늘 소금빵 안 팔겠습니다\", \"action\": \"팔짱 끼고 고개 돌림\", "
    "\"shot\": {\"size\": \"보통\", \"angle\": \"정면\", \"count\": \"혼자\"}, \"expression\": \"새침함\", "
    "\"pose\": \"팔짱\", \"place\": \"가게 안\", \"props\": [\"빵 진열대\"], \"light\": \"\"},\n"
    " {\"n\": 2, \"line\": \"...라고 하려 했는데\", \"action\": \"멀리서 손님 무리가 몰려옴\", "
    "\"shot\": {\"size\": \"아주작게\", \"angle\": \"정면\", \"count\": \"여럿\"}, \"expression\": \"놀람\", "
    "\"pose\": \"서있기\", \"place\": \"가게 앞\", \"props\": [\"고양이 손님\", \"강아지 손님\"], \"light\": \"아침 햇살\"},\n"
    " {\"n\": 3, \"line\": \"하겠습니다. 1시간 만에 매진\", \"action\": \"빈 쟁반을 들고 땀 흘림\", "
    "\"shot\": {\"size\": \"아주크게\", \"angle\": \"아래에서\", \"count\": \"혼자\"}, \"expression\": \"당황, 땀\", "
    "\"pose\": \"빈 쟁반 들기\", \"place\": \"가게 안\", \"props\": [\"빈 쟁반\"], \"light\": \"\"},\n"
    " {\"n\": 4, \"line\": \"내일도 7시에 굽겠습니다 — 연남로 12\", \"action\": \"가게 앞에서 손 흔듦\", "
    "\"shot\": {\"size\": \"작게\", \"angle\": \"정면\", \"count\": \"혼자\"}, \"expression\": \"활짝 웃음\", "
    "\"pose\": \"손 흔들기\", \"place\": \"가게 앞\", \"props\": [\"간판\"], \"light\": \"저녁 노을\"}]}\n\n"
    "예시 2 — 밈 '100드립', 크루아상 30개:\n"
    "{\"title\": \"백 개는 구웠지\", \"cuts\": [\n"
    " {\"n\": 1, \"line\": \"오늘 크루아상 백 개 구웠지\", \"action\": \"자신만만하게 쟁반 들기\", "
    "\"shot\": {\"size\": \"크게\", \"angle\": \"정면\", \"count\": \"혼자\"}, \"expression\": \"자신만만\", "
    "\"pose\": \"쟁반 들기\", \"place\": \"주방\", \"props\": [\"크루아상\", \"쟁반\"], \"light\": \"\"},\n"
    " {\"n\": 2, \"line\": \"...서른 개인데\", \"action\": \"작은 진열대를 멀리서\", "
    "\"shot\": {\"size\": \"아주작게\", \"angle\": \"위에서\", \"count\": \"혼자\"}, \"expression\": \"머쓱함\", "
    "\"pose\": \"서있기\", \"place\": \"가게 안\", \"props\": [\"빵 진열대\"], \"light\": \"\"},\n"
    " {\"n\": 3, \"line\": \"그래도 백 개처럼 맛있지\", \"action\": \"크루아상을 한 입 물고 눈 감음\", "
    "\"shot\": {\"size\": \"아주크게\", \"angle\": \"옆에서\", \"count\": \"혼자\"}, \"expression\": \"행복, 눈 감음\", "
    "\"pose\": \"빵 먹기\", \"place\": \"가게 안\", \"props\": [\"크루아상\"], \"light\": \"\"},\n"
    " {\"n\": 4, \"line\": \"오전 7시부터 — 연남로 12\", \"action\": \"가게 앞에서 인사\", "
    "\"shot\": {\"size\": \"작게\", \"angle\": \"정면\", \"count\": \"혼자\"}, \"expression\": \"미소\", "
    "\"pose\": \"인사\", \"place\": \"가게 앞\", \"props\": [\"간판\"], \"light\": \"아침 햇살\"}]}\n\n"
    "위 예시처럼 네 컷의 shot.size를 서로 다르게 섞어 리듬을 만든다. 예시는 형식을 보여줄 뿐이다 — "
    "예시의 대사·시간·주소·표정·소품을 베끼지 말고, 주어진 밈과 이 가게의 실제 정보(영업시간·주소·생산 기록)로 "
    "새로 쓴다. 같은 형식의 JSON 하나만 출력한다."
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
        shot = c.get("shot") if isinstance(c.get("shot"), dict) else {}

        def pick(val, choices, default):
            v = str(val or "").strip()
            return v if v in choices else default

        props = c.get("props") or []
        cuts.append({
            "n": i + 1,
            "line": str(c.get("line") or "").strip(),
            "action": str(c.get("action") or "").strip(),   # 화면 표시용 한 줄 요약
            "short": str(c.get("line") or "")[:14],
            # 팀장 슬롯 시트의 컷 층. 닫힌 세 칸은 선택지 밖이면 안전한 기본값으로.
            "slots": {
                "shot": {
                    "size": pick(shot.get("size"), SHOT_SIZE_CHOICES, "작게"),
                    "angle": pick(shot.get("angle"), SHOT_ANGLE_CHOICES, "정면"),
                    "count": pick(shot.get("count"), SHOT_COUNT_CHOICES, "혼자"),
                },
                "expression": str(c.get("expression") or "").strip(),
                "pose": str(c.get("pose") or "").strip(),
                "place": str(c.get("place") or "").strip(),
                "props": [str(p) for p in props] if isinstance(props, list) else [str(props)],
                "light": str(c.get("light") or "").strip(),
            },
        })
    if len(cuts) < 2 or any(not c["line"] for c in cuts):
        raise RuntimeError("스토리 형식이 어긋났어요 — 다시 제안받아 주세요")
    return {"title": str(data.get("title") or meme_title), "cuts": cuts}
