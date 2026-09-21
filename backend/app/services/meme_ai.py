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

CARD_KEYS = ("definition", "why", "template", "visual", "industries", "avoid", "understanding", "humor_type")

# 밈이 웃기는 방식은 하나가 아니다. 종류마다 네 컷에 웃음을 배치하는 법이 달라서, 카드에 종류를 하나
# 적어 두고 스토리 지시문에 그 종류의 레시피만 붙인다(2026-09-21 사용자: "유머를 선택했을 때 유머
# 프롬프트가 필요"). 종류는 다섯 개로 고정 — GPT가 지어내지 못하게 선택지로 준다.
HUMOR_TYPES = {
    "반전": "1~2컷은 진지하고 작게(대사·표정 모두 정색), 3컷에서 **실제 규모·현실을 그림으로** 보여준다 — 카드의 visual 이 "
            "곧 3컷의 shot·pose·props·place 다. 대사로 설명하지 말고 그림 대비로 웃긴다. 3컷은 shot.size 를 1~2컷과 반대로 잡는다.",
    "말장난": "밈의 어미·낱말을 네 컷 대사 **끝마다** 붙인다. 컷이 갈수록 더 무리한 자리에 붙이고, 3컷이 가장 억지스럽다. "
              "4컷은 캐릭터도 스스로 어이없어하거나(땀·눈 돌림) 손님이 반응한다.",
    "번복": "1컷 단호한 선언 → 2컷 그 이유(진지) → 3컷 정반대 선언(생산 기록의 숫자를 근거로) → 4컷 뻔뻔한 마무리. "
            "1컷과 3컷의 표정·자세를 정확히 반대로 잡는다(팔짱↔두 손 들기, 새침↔활짝).",
    "되묻기": "캐릭터가 뻔한 것을 아주 진지하게 묻고(1~2컷), 동물 손님이 어이없어한다(3컷, shot.count 여럿). "
              "4컷에서 캐릭터는 끝까지 진지하다 — 깨닫지 않는 게 웃음이다.",
    "공감": "누구나 겪는 상황을 빵집 하루로 옮긴다. 과장 대신 작은 디테일(땀 한 방울, 빈 쟁반, 시계)로 웃긴다. "
            "3컷은 shot.size 아주크게로 표정 하나에 건다.",
}

# 그림 모델이 알아듣는 구도 태그만 허용한다. 자연어 카메라 지시("입구 클로즈업")는 여기로 매핑된다.
CAMERA_TAGS = ("straight-on", "close-up", "from_side", "from_below", "from_above", "wide_shot")

_CARD_PROMPT = (
    "당신은 한국 SNS 밈을 광고 기획자에게 설명하는 편집자다. 아래 밈 원문(뉴스레터 본문 등)을 읽고 "
    "JSON 하나만 출력한다. 키: definition(한 줄 정의), why(유행 이유), template(말 틀 — 대괄호 자리표시로), "
    "visual(그림으로 옮길 때의 시각 요소), industries(어울리는 업종 배열), avoid(피할 것 배열), "
    "understanding(원문만으로 이 밈을 얼마나 확실히 이해했는지 0~1 숫자), "
    f"humor_type(이 밈이 웃기는 방식 — 반드시 다음 중 하나: {' | '.join(HUMOR_TYPES)}). "
    "humor_type 기준: 반전=작게 말하고 크게 보여주는 대비 / 말장난=어미·낱말 비틀기 / 번복=말을 뒤집기 / "
    "되묻기=뻔한 걸 진지하게 묻기 / 공감=누구나 겪는 상황. "
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
    "당신은 동네 빵집의 SNS 네컷 만화를 기획하는 개그 작가다. 주어진 밈 카드와 가게 정보로 4컷 스토리를 JSON 하나로 출력한다.\n"
    "주인공은 가게 마스코트 한 마리다. 사람 손님은 그리지 않는다 — 손님이 필요하면 동물 손님으로 적는다. "
    "가게 정보에 없는 가격·할인은 지어내지 않는다.\n\n"
    "밈 카드를 이렇게 쓴다:\n"
    "  template  말 틀 — 네 컷 중 세 컷 이상의 대사에서 **자리표시를 이 가게의 것으로 채워** 실제로 쓴다\n"
    "  why       웃음 포인트 — 이게 3컷에서 터져야 한다. 3컷을 먼저 정하고 1·2컷을 거꾸로 짠다\n"
    "  visual    그림 요소 — 3컷의 shot·pose·props·place 로 옮긴다. 대사로 설명하지 말고 그림으로 보인다\n"
    "  avoid     어기지 않는다\n"
    "네 컷의 역할: 1컷 상황(말 틀 첫 사용) → 2컷 키우기(기대·긴장) → 3컷 웃음 포인트(why 실현) → 4컷 마무리 — "
    "마지막 컷은 가게 이름·영업시간 같은 실제 정보로 끝낸다.\n"
    "[유머 종류]로 지정된 레시피를 따른다. 마지막에 why_funny 한 줄로 '몇 컷에서 왜 웃긴가'를 스스로 적는다 — "
    "이 줄을 쓰다가 웃음 포인트가 없으면 3컷을 다시 짠다.\n\n"
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
    # 예시는 형식과 레시피를 보여주는 용도라 앱에 저장된 밈과 겹치지 않는 밈으로 짠다 — 같은 밈이 예시에
    # 있으면 GPT가 예시를 그대로 베낀다(09-21 실측: 100드립 예시 → 100드립 회차 컷 1·2 슬롯값 동일).
    # 예시는 **빵집이 아닌 가게**(분식집·꽃집)로 짠다. 빵집 예시를 주면 GPT가 대사·소품을 그대로 베낀다
    # (09-21 실측: 같은 유머 종류 예시의 컷 2·3·4 를 소품만 바꿔 복사). 업종이 다르면 옮겨 쓸 수밖에 없다.
    "예시 1 — 분식집. 밈 '○○각'(말 끝에 '~각'을 붙여 확신하는 말장난), 유머 종류 말장난, 김밥 15줄, 마스코트 고슴도치:\n"
    "{\"title\": \"매진각\", \"cuts\": [\n"
    " {\"n\": 1, \"line\": \"오늘 김밥 열다섯 줄. 이건 매진각\", \"action\": \"김밥 접시 들고 확신\", "
    "\"shot\": {\"size\": \"보통\", \"angle\": \"정면\", \"count\": \"혼자\"}, \"expression\": \"확신, 반짝이는 눈\", "
    "\"pose\": \"접시 들기\", \"place\": \"가게 안\", \"props\": [\"김밥\", \"접시\"], \"light\": \"\"},\n"
    " {\"n\": 2, \"line\": \"비 오네... 이것도 매진각\", \"action\": \"창밖 비를 보는 텅 빈 가게\", "
    "\"shot\": {\"size\": \"아주작게\", \"angle\": \"옆에서\", \"count\": \"혼자\"}, \"expression\": \"굳은 미소\", "
    "\"pose\": \"창밖 보기\", \"place\": \"가게 안\", \"props\": [\"창문\", \"비\"], \"light\": \"흐림\"},\n"
    " {\"n\": 3, \"line\": \"우산 쓴 손님 한 마리. 매진각각각\", \"action\": \"손님 하나에 과하게 감격\", "
    "\"shot\": {\"size\": \"아주크게\", \"angle\": \"아래에서\", \"count\": \"여럿\"}, \"expression\": \"감격, 눈물\", "
    "\"pose\": \"두 손 모으기\", \"place\": \"가게 앞\", \"props\": [\"우산\", \"고양이 손님\"], \"light\": \"흐림\"},\n"
    " {\"n\": 4, \"line\": \"내일은 맑음각. 김밥 열다섯 줄 또 쌉니다\", \"action\": \"김밥 말며 멋쩍게\", "
    "\"shot\": {\"size\": \"작게\", \"angle\": \"정면\", \"count\": \"혼자\"}, \"expression\": \"멋쩍은 웃음, 땀\", "
    "\"pose\": \"김밥 말기\", \"place\": \"주방\", \"props\": [\"김밥\", \"김\"], \"light\": \"\"}],\n"
    " \"why_funny\": \"3컷 — '매진각'이 갈수록 근거 없는 자리에 붙다가 손님 한 마리에 '각각각'으로 터진다. 어미 남용 자체가 웃음\"}\n\n"
    "예시 2 — 꽃집. 밈 '그게 되네'(안 될 것 같은 게 되는 반전), 유머 종류 반전, 장미 40송이 입고, 마스코트 두더지:\n"
    "{\"title\": \"그게 되네\", \"cuts\": [\n"
    " {\"n\": 1, \"line\": \"장미 마흔 송이는 무리지...\", \"action\": \"꽃통 앞에서 걱정\", "
    "\"shot\": {\"size\": \"크게\", \"angle\": \"옆에서\", \"count\": \"혼자\"}, \"expression\": \"걱정, 땀\", "
    "\"pose\": \"턱 짚기\", \"place\": \"가게 안\", \"props\": [\"장미\", \"꽃통\"], \"light\": \"\"},\n"
    " {\"n\": 2, \"line\": \"반이라도 팔리면 다행\", \"action\": \"장미를 한 송이씩 조심스레 꽂음\", "
    "\"shot\": {\"size\": \"보통\", \"angle\": \"정면\", \"count\": \"혼자\"}, \"expression\": \"긴장\", "
    "\"pose\": \"꽃 꽂기\", \"place\": \"가게 안\", \"props\": [\"장미\", \"꽃병\"], \"light\": \"아침 햇살\"},\n"
    " {\"n\": 3, \"line\": \"\", \"action\": \"한 시간 뒤, 가게 밖까지 줄 선 동물 손님들과 텅 빈 꽃통\", "
    "\"shot\": {\"size\": \"아주작게\", \"angle\": \"정면\", \"count\": \"여럿\"}, \"expression\": \"멍함\", "
    "\"pose\": \"빈 꽃통 들기\", \"place\": \"가게 앞\", \"props\": [\"고양이 손님\", \"강아지 손님\", \"빈 꽃통\"], \"light\": \"아침 햇살\"},\n"
    " {\"n\": 4, \"line\": \"...그게 되네. 내일은 여든 송이\", \"action\": \"팔 걷어붙이고 결의\", "
    "\"shot\": {\"size\": \"작게\", \"angle\": \"아래에서\", \"count\": \"혼자\"}, \"expression\": \"불타는 눈\", "
    "\"pose\": \"주먹 불끈\", \"place\": \"가게 안\", \"props\": [\"꽃통\"], \"light\": \"\"}],\n"
    " \"why_funny\": \"3컷 — 1·2컷은 걱정하며 작게 잡고, 3컷은 대사를 비우고 줄과 빈 꽃통(visual)만으로 규모를 보여줘 대비가 터진다\"}\n\n"
    "위 예시는 다른 업종이다 — 형식과 레시피만 가져오고 대사·소품·장소는 **이 빵집과 생산 기록**으로 새로 쓴다. "
    "네 컷의 shot.size는 서로 다르게 섞어 리듬을 만든다. 대사를 비운 컷은 한 컷까지만. 같은 형식의 JSON 하나만 출력한다."
)

# 판별도 규칙보다 예시. 규칙만 줬을 때 '하겠습니다/안 하겠습니다'를 번복이 아니라 공감으로 골랐다(09-21).
_HUMOR_CLASSIFY_PROMPT = (
    "아래 밈 카드가 웃기는 방식을 다음 중 하나로만 고른다: " + " | ".join(HUMOR_TYPES) + ".\n"
    "예시:\n"
    "  '100명 넘겠지?' — 큰 규모를 일부러 작은 기준으로 말함 → 반전\n"
    "  '소금빵삐', '~각' — 어미·낱말을 붙이거나 비틂 → 말장난\n"
    "  '하겠습니다 / 안 하겠습니다', '포기와 진행을 번갈아' — 같은 말을 뒤집어 반복 → 번복\n"
    "  '누가 돌아왔게~? / 그래, ○○이 돌아왔다' — 뻔한 답을 진지하게 묻고 답함 → 되묻기\n"
    "  '월요일 출근길', '퇴근 5분 전' — 누구나 겪는 상황 그 자체 → 공감\n"
    "말 틀(template)이 뒤집기·반복이면 감정이 공감돼도 번복이다. JSON {\"humor_type\": str, \"reason\": 한 줄} 만 출력한다."
)


def classify_humor(card: dict) -> tuple[str, str]:
    """카드에 humor_type 이 없을 때(옛 카드) 한 번 골라 준다. (종류, 이유). 선택지 밖이면 '공감'."""
    data = _json_chat(_HUMOR_CLASSIFY_PROMPT, json.dumps(card, ensure_ascii=False), temperature=0)
    kind = str(data.get("humor_type") or "").strip()
    return (kind if kind in HUMOR_TYPES else "공감"), str(data.get("reason") or "")


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
    kind = str(card.get("humor_type") or "").strip()
    card["humor_type"] = kind if kind in HUMOR_TYPES else classify_humor(card)[0]
    return card


def story_user_message(card: dict, meme_title: str, store: dict, prods: list[dict], ad: dict, mascot: str) -> str:
    """스토리 GPT에 보내는 유저 메시지. 보고서에서 그대로 보여주려고 따로 뺐다."""
    prod_lines = [
        f"- {p.get('name')} {p.get('qty') or ''} ({p.get('date') or ''} {p.get('time') or ''}"
        + (f", 매진 {p['sold_out']}" if p.get("sold_out") else "") + ")"
        for p in prods
    ] or ["- (기록 없음)"]
    kind = card.get("humor_type") or "공감"
    return (
        f"[밈 카드: {meme_title}]\n{json.dumps(card, ensure_ascii=False, indent=1)}\n\n"
        f"[유머 종류] {kind}\n레시피: {HUMOR_TYPES.get(kind, HUMOR_TYPES['공감'])}\n\n"
        f"[가게]\n업종: {store.get('category') or '빵집'}\n주소: {store.get('address') or ''}\n"
        f"영업시간: {store.get('hours') or ''}\n소개: {store.get('desc') or ''}\n"
        f"[생산 기록]\n" + "\n".join(prod_lines) + "\n\n"
        f"[광고] 종류: {ad.get('ad_type') or ''} / 컨셉: {ad.get('ad_concept') or ''}\n"
        f"[마스코트] {mascot or '가게 마스코트'}"
    )


def propose_story(card: dict, meme_title: str, store: dict, prods: list[dict], ad: dict, mascot: str) -> dict:
    """카드 + 가게 정보 → {title, humor_type, why_funny, cuts[4]}. 컷은 line/action/slots 를 갖는다.

    카드에 humor_type 이 없으면(옛 카드) 여기서 한 번 골라 card 에 채워 넣는다 — 호출부가 저장하면
    다음부터는 안 묻는다."""
    if str(card.get("humor_type") or "") not in HUMOR_TYPES:
        card["humor_type"] = classify_humor(card)[0]
    user = story_user_message(card, meme_title, store, prods, ad, mascot)
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
    # 대사가 빈 컷은 허용한다 — 반전 레시피가 "3컷은 대사 없이 그림으로"라 일부러 비운다(말풍선은 안 그려진다).
    # 대사·동작이 둘 다 빈 컷이나, 대사 있는 컷이 둘 미만이면 형식 오류.
    if len(cuts) < 2 or any(not c["line"] and not c["action"] for c in cuts) \
            or sum(1 for c in cuts if c["line"]) < 2:
        raise RuntimeError("스토리 형식이 어긋났어요 — 다시 제안받아 주세요")
    return {"title": str(data.get("title") or meme_title), "cuts": cuts,
            "humor_type": card["humor_type"], "why_funny": str(data.get("why_funny") or "").strip()}
