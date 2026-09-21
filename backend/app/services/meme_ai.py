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

# 광고 느낌은 **사장님이 화면에서 고른다** (frontend Ad.jsx / Storyboard.jsx 의 AD_CONCEPTS → ad_concept).
# 느낌마다 네 컷을 짜는 법이 달라서, 고른 느낌의 레시피만 스토리 지시문에 붙인다. 밈 카드는 네 느낌 모두
# 쓰되 쓰는 정도가 다르다 — 유쾌함은 밈이 주인공, 담백함은 말 틀 한 번만.
# (처음엔 밈을 GPT가 반전·말장난 등으로 자동 분류하게 했는데, 느낌은 사용자가 고르는 것이라 되돌렸다. 09-21)
AD_CONCEPTS = ("유쾌함", "감성", "정보형", "담백함")
CONCEPT_RECIPES = {
    "유쾌함": "밈이 주인공이다. 카드의 template 을 세 컷 이상 대사에 실제로 쓰고, why(웃음 포인트)가 **3컷에서 터지게** 3컷을 먼저 "
              "정한 뒤 1·2컷을 거꾸로 짠다. visual 은 3컷의 shot·pose·props·place 로 옮긴다 — 대사로 설명하지 말고 그림으로 보인다. "
              "1·2컷은 작게·정색, 3컷은 shot.size 를 반대로(아주크게 또는 여럿이면 아주작게). 4컷은 캐릭터가 멋쩍어하거나 뻔뻔하게 마무리. "
              "필요하면 3컷 대사를 비워 그림만으로 웃긴다.",
    "감성": "웃기려 하지 않는다. 밈은 말 틀만 1·4컷에 조용히 쓴다. 새벽에 굽는 손, 오븐의 김, 창으로 드는 빛 같은 작은 디테일로 "
            "하루를 보여준다. light 슬롯을 컷마다 채운다(새벽 어스름 → 아침 햇살 → 낮 → 노을). 3컷은 shot.size 아주크게로 "
            "표정 하나(눈 감음·미소)에 건다. 대사는 짧고 잔잔하게, 감탄사·느낌표 없이.",
    "정보형": "사실이 주인공이다. 생산 기록의 무엇을·몇 개·몇 시를 컷마다 하나씩 대사에 넣는다(1컷 무엇을, 2컷 몇 개, 3컷 몇 시·매진, "
              "4컷 어디서). 밈은 1컷 도입에만 쓴다. 과장·비유 없이, shot.size 는 보통·크게 위주로 빵이 잘 보이게, props 에 실제 빵 이름. "
              "표정은 차분한 미소 하나로 고정한다.",
    "담백함": "말을 아낀다. 대사는 열 자 안팎, 감탄사·과장 없음. 밈의 말 틀은 딱 한 번(3컷)만. 네 컷 중 한 컷은 대사를 비운다. "
              "배경은 단순하게(place 한 단어, props 는 하나), light 는 비운다. 표정도 무표정·옅은 미소 둘만 쓴다. 여백이 멋이다.",
}

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
    "당신은 동네 빵집의 SNS 네컷 만화를 기획하는 작가다. 주어진 밈 카드·가게 정보·광고 느낌으로 4컷 스토리를 JSON 하나로 출력한다.\n"
    "주인공은 가게 마스코트 한 마리다. 사람 손님은 그리지 않는다 — 손님이 필요하면 동물 손님으로 적는다. "
    "가게 정보에 없는 가격·할인은 지어내지 않는다. 카드의 avoid 를 어기지 않는다.\n\n"
    "밈 카드의 칸: template(말 틀 — 자리표시를 이 가게의 것으로 채워 쓴다) · why(웃음 포인트) · visual(그림 요소). "
    "**어느 정도로 쓰는지는 [광고 느낌]의 레시피가 정한다** — 유쾌함은 밈이 주인공, 담백함은 말 틀 한 번뿐이다.\n"
    "네 컷의 역할: 1컷 상황 → 2컷 키우기 → 3컷 핵심(느낌이 가장 드러나는 컷) → 4컷 마무리 — "
    "마지막 컷은 가게 이름·영업시간 같은 실제 정보로 끝낸다.\n"
    "마지막에 concept_check 한 줄로 '고른 느낌이 몇 컷에서 어떻게 드러나는가'를 스스로 적는다 — "
    "이 줄을 쓰다가 드러나는 데가 없으면 3컷을 다시 짠다.\n\n"
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
    "예시 1 — 분식집. 밈 '○○각'(말 끝에 '~각'을 붙여 확신하는 말장난), 광고 느낌 유쾌함, 김밥 15줄, 마스코트 고슴도치:\n"
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
    " \"concept_check\": \"유쾌함 — 3컷에서 '매진각'이 갈수록 근거 없는 자리에 붙다가 손님 한 마리에 '각각각'으로 터진다\"}\n\n"
    "예시 2 — 꽃집. 밈 '그게 되네'(안 될 것 같은 게 되는 반전), 광고 느낌 유쾌함, 장미 40송이 입고, 마스코트 두더지:\n"
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
    " \"concept_check\": \"유쾌함 — 1·2컷은 걱정하며 작게 잡고, 3컷은 대사를 비우고 줄과 빈 꽃통(visual)만으로 규모를 보여줘 대비가 터진다\"}\n\n"
    "위 두 예시는 유쾌함이다. 감성·정보형·담백함을 골랐을 땐 같은 형식으로 쓰되 그 느낌의 레시피를 따른다 — "
    "감성은 웃기지 않고, 정보형은 숫자·시간이 대사에 있고, 담백함은 열 자 안팎이다.\n\n"
    "위 예시는 다른 업종이다 — 형식과 레시피만 가져오고 대사·소품·장소는 **이 빵집과 생산 기록**으로 새로 쓴다. "
    "네 컷의 shot.size는 서로 다르게 섞어 리듬을 만든다. 대사를 비운 컷은 한 컷까지만. 같은 형식의 JSON 하나만 출력한다."
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


def story_user_message(card: dict, meme_title: str, store: dict, prods: list[dict], ad: dict, mascot: str) -> str:
    """스토리 GPT에 보내는 유저 메시지. 보고서에서 그대로 보여주려고 따로 뺐다."""
    prod_lines = [
        f"- {p.get('name')} {p.get('qty') or ''} ({p.get('date') or ''} {p.get('time') or ''}"
        + (f", 매진 {p['sold_out']}" if p.get("sold_out") else "") + ")"
        for p in prods
    ] or ["- (기록 없음)"]
    concept = concept_of(ad)
    return (
        f"[밈 카드: {meme_title}]\n{json.dumps(card, ensure_ascii=False, indent=1)}\n\n"
        f"[광고 느낌] {concept}\n레시피: {CONCEPT_RECIPES[concept]}\n\n"
        f"[가게]\n업종: {store.get('category') or '빵집'}\n주소: {store.get('address') or ''}\n"
        f"영업시간: {store.get('hours') or ''}\n소개: {store.get('desc') or ''}\n"
        f"[생산 기록]\n" + "\n".join(prod_lines) + "\n\n"
        f"[광고] 종류: {ad.get('ad_type') or ''}\n"
        f"[마스코트] {mascot or '가게 마스코트'}"
    )


def concept_of(ad: dict) -> str:
    """화면에서 고른 광고 느낌. 선택지 밖(빈 값·옛 데이터)이면 유쾌함 — 밈 기반 광고의 기본값."""
    c = str(ad.get("ad_concept") or "").strip()
    return c if c in CONCEPT_RECIPES else "유쾌함"


def propose_story(card: dict, meme_title: str, store: dict, prods: list[dict], ad: dict, mascot: str) -> dict:
    """카드 + 가게 정보 + 광고 느낌 → {title, concept, concept_check, cuts[4]}. 컷은 line/action/slots 를 갖는다."""
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
            "concept": concept_of(ad), "concept_check": str(data.get("concept_check") or "").strip()}
