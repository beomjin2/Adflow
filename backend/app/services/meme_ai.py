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

# 스토리는 두 사람이 만든다 — **작가**(대사 먼저, 3편 쓰고 고른다) → **연출**(고른 대사를 슬롯으로).
# 한 번에 10칸을 채우게 하면 GPT가 형식 맞추는 데 힘을 다 써서 대사가 남는 힘으로 나왔다(09-21 사용자:
# "대사가 재미도 감동도 없다"). 대사를 먼저, 그림 지시는 나중에. 작가는 temperature 0.9, 연출은 0.3.
_SCRIPT_PROMPT = (
    "당신은 동네 빵집 SNS 네컷 만화의 **대사 작가**다. 대사만 쓴다 — 그림 지시는 다음 사람(연출)이 한다.\n\n"
    "[주인공] 마스코트 시트가 주어진다. 말투는 시트의 성격·나이·취미·능력에서 나온다 — 느긋하면 느리게 끊어 말하고, "
    "세 살이면 세 살처럼, 새벽에 굽는 게 자랑이면 그게 튀어나온다. 네 컷 내내 같은 사람이 말한다.\n\n"
    "[밈 적합성 — 맨 먼저 한다] template 의 자리표시에 넣을 것을 가게 정보에서 찾는다. 밈이 기대하는 규모·상황과 가게 숫자가 "
    "안 맞으면(예: '100개 넘겠지?'는 아주 많은 것에 쓰는 말인데 빵은 20개) 숫자를 억지로 넣지 않는다. 규모가 맞는 다른 대상으로 "
    "옮긴다 — 새벽 4시부터 선 시간, 골목 끝까지 선 줄, 동네에 퍼진 냄새, 반죽을 치댄 횟수, 사장님의 다크서클. "
    "옮긴 이유를 fit.note 에, 옮긴 대상을 fit.target 에 적는다. 도저히 안 맞으면 fit.ok=false 로 표시하고 그래도 가장 덜 어색한 방식으로 쓴다. "
    "옮기기 보기: 빵 20개에 '100개 넘겠지?' ✗ → 새벽 4시부터 선 사장님에게 '오늘 100분은 잤겠지?' ✓ / 골목 끝 줄에 '100명은 넘겠지?' ✓ / "
    "반죽 치댄 횟수에 '100번은 쳤겠지?' ✓.\n\n"
    "[장소] beats 의 장소는 주방·가게 안·가게 앞·골목·창가 중에서만. 가게 밖 먼 곳(해변·공원)은 쓰지 않는다.\n\n"
    "[광고 느낌] 주어진 레시피를 따른다. 유쾌함이면 4컷이 펀치라인, 감성이면 4컷이 여운, 정보형이면 4컷이 숫자, 담백함이면 4컷이 한 마디.\n\n"
    "[하지 말 것] 주소·영업시간·'내일도 오세요' 같은 광고 문구를 대사에 넣지 않는다 — 그건 그림 아래 캡션이 따로 맡는다. "
    "가격·할인을 지어내지 않는다. 사람 손님은 동물 손님으로. 카드의 avoid 를 어기지 않는다.\n\n"
    "[쓰는 법] 초안을 **3편** 쓴다. 편마다 title, lines(대사 4개 — 컷 하나는 비워도 된다, 한 컷 15자 안팎), "
    "beats(컷마다 무슨 일이 일어나는지 한 줄 — 어디서·무엇을·누가 있나), voice(이 편에서 말투가 드러나는 대사 하나). "
    "세 편을 '읽고 웃기거나 뭉클한가 / 밈이 억지 없이 붙었나 / 4컷이 끝을 맺는가 / 말투가 있는가'로 비교해 why 에 편마다 한 줄씩 "
    "평을 먼저 쓰고, 그 평과 맞는 번호를 best(0·1·2)에 적는다. voice 가 '없음'인 편은 고르지 않는다.\n\n"
    "출력 JSON: {\"fit\": {\"ok\": bool, \"note\": str, \"target\": str}, \"drafts\": [{\"title\", \"lines\": [4], \"beats\": [4], \"voice\"} ×3], "
    "\"why\": str, \"best\": int}\n\n"
    "예시 — 분식집, 밈 '그게 되네'(안 될 것 같은 게 되는 반전), 유쾌함, 마스코트 고슴도치 '콩이'(소심함, 취미 낮잠, 김밥 40줄):\n"
    "{\"fit\": {\"ok\": true, \"note\": \"'안 될 것 같은 일'이 필요한데 40줄은 소심한 콩이에겐 충분히 무리다\", \"target\": \"김밥 40줄\"},\n"
    " \"drafts\": [\n"
    "  {\"title\": \"그게 되네\", \"lines\": [\"마흔 줄은... 좀 무리 아닐까\", \"반만 팔려도 낮잠 잘 수 있어\", \"\", \"...그게 되네. 낮잠은 내일\"], "
    "\"beats\": [\"주방, 김밥 산더미 앞에서 움츠림\", \"진열대에 한 줄씩 조심스레 놓음\", \"한 시간 뒤, 가게 밖까지 줄 선 동물 손님과 빈 접시\", \"빈 접시 안고 멍하니 서 있음\"], "
    "\"voice\": \"'반만 팔려도 낮잠 잘 수 있어' — 소심하고 낮잠이 목표인 콩이\"},\n"
    "  {\"title\": \"낮잠각\", \"lines\": [\"오늘 마흔 줄 쌌다\", \"...나 왜 그랬지\", \"손님: 다 주세요\", \"그게 되네?\"], "
    "\"beats\": [\"김밥 줄 세는 콩이\", \"창밖 텅 빈 거리\", \"고양이 손님이 접시째 가리킴\", \"콩이 눈 동그래짐\"], \"voice\": \"'...나 왜 그랬지' — 소심함\"},\n"
    "  {\"title\": \"40줄\", \"lines\": [\"김밥 40줄 준비\", \"팔릴까\", \"팔렸다\", \"내일도 40줄\"], \"beats\": [\"주방\", \"가게\", \"빈 접시\", \"주방\"], \"voice\": \"없음\"}],\n"
    " \"best\": 0, \"why\": \"0번만 3컷을 대사 없이 그림으로 터뜨리고, 4컷 '낮잠은 내일'이 콩이 말투로 끝맺는다. 2번은 밈이 붙었을 뿐 인물이 없다\"}\n\n"
    "예시는 다른 업종이다 — 형식만 가져오고 대사는 이 가게·이 마스코트로 새로 쓴다. JSON 하나만 출력한다."
)

# 컷 층의 닫힌 슬롯 선택지. chat_ai 의 표와 키가 같아야 한다.
SHOT_POSITION_CHOICES = ("왼쪽", "가운데", "오른쪽")   # 캐릭터를 화면 어느 쪽에 두나 — 태그가 아니라 넓게 뽑아 자른다
GAZE_CHOICES = ("정면", "옆", "아래", "상대", "눈감음")

_DIRECT_PROMPT = (
    "당신은 네컷 만화의 **연출**이다. 작가가 고른 대사(lines)와 컷 상황(beats)을 받아 컷마다 그림 슬롯을 채운다. "
    "대사는 바꾸지 않는다.\n\n"
    "컷마다 아래 칸을 채운다. shot 과 gaze 는 반드시 주어진 선택지 중 하나만 쓴다.\n"
    f"  shot.size      {' | '.join(SHOT_SIZE_CHOICES)}  (캐릭터가 화면에서 얼마나 크게)\n"
    f"  shot.angle     {' | '.join(SHOT_ANGLE_CHOICES)}\n"
    f"  shot.count     {' | '.join(SHOT_COUNT_CHOICES)}\n"
    f"  shot.position  {' | '.join(SHOT_POSITION_CHOICES)}  (캐릭터를 어느 쪽에 두고 반대쪽을 비우나)\n"
    f"  gaze           {' | '.join(GAZE_CHOICES)}  (시선 — 정면은 카메라를 본다)\n"
    "  expression     표정 — 짧은 한국어 구\n"
    "  pose           동작 — 짧은 한국어 구\n"
    "  place          장소 — 한 단어\n"
    "  props          소품 — 단어 배열\n"
    "  light          빛 — 한 단어 또는 빈 문자열\n\n"
    "만화 구도의 기본 — 예시가 보여주는 대로:\n"
    "  · 대사가 있는 컷은 캐릭터를 **왼쪽이나 오른쪽**에 두고 반대쪽을 비운다(말풍선 자리). 가운데는 대사 없는 컷이나 여럿 컷에만.\n"
    "  · 정면(angle)은 네 컷 중 최대 두 컷, 카메라를 보는 시선(gaze 정면)은 최대 한 컷. 나머지는 옆·아래·상대(손님이나 빵)를 본다.\n"
    "  · size 는 네 컷이 서로 다르게. beats 에 '멀리서·줄·거리'가 있으면 아주작게, 표정 하나에 거는 컷은 아주크게.\n"
    "  · 감성이면 light 를 네 컷 다 채운다. 담백함이면 props 하나뿐이어도 그중 하나는 빵.\n\n"
    "예시 — 분식집 '그게 되네'(유쾌함), lines [\"마흔 줄은... 좀 무리 아닐까\", \"반만 팔려도 낮잠 잘 수 있어\", \"\", \"...그게 되네. 낮잠은 내일\"]:\n"
    "{\"cuts\": [\n"
    " {\"n\": 1, \"shot\": {\"size\": \"크게\", \"angle\": \"옆에서\", \"count\": \"혼자\", \"position\": \"왼쪽\"}, \"gaze\": \"아래\", "
    "\"expression\": \"걱정, 땀\", \"pose\": \"움츠리기\", \"place\": \"주방\", \"props\": [\"김밥\", \"접시\"], \"light\": \"\"},\n"
    " {\"n\": 2, \"shot\": {\"size\": \"보통\", \"angle\": \"위에서\", \"count\": \"혼자\", \"position\": \"오른쪽\"}, \"gaze\": \"옆\", "
    "\"expression\": \"긴장\", \"pose\": \"접시 놓기\", \"place\": \"가게 안\", \"props\": [\"김밥\", \"진열대\"], \"light\": \"아침 햇살\"},\n"
    " {\"n\": 3, \"shot\": {\"size\": \"아주작게\", \"angle\": \"정면\", \"count\": \"여럿\", \"position\": \"가운데\"}, \"gaze\": \"상대\", "
    "\"expression\": \"멍함\", \"pose\": \"빈 접시 들기\", \"place\": \"가게 앞\", \"props\": [\"고양이 손님\", \"강아지 손님\", \"빈 접시\"], \"light\": \"아침 햇살\"},\n"
    " {\"n\": 4, \"shot\": {\"size\": \"아주크게\", \"angle\": \"아래에서\", \"count\": \"혼자\", \"position\": \"왼쪽\"}, \"gaze\": \"정면\", "
    "\"expression\": \"멍한 미소\", \"pose\": \"빈 접시 안기\", \"place\": \"가게 안\", \"props\": [\"빈 접시\"], \"light\": \"\"}]}\n\n"
    "예시는 다른 업종이다 — 형식과 구도 원칙만 가져온다. JSON 하나만 출력한다."
)


def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY가 비어 있어 밈 카드·스토리를 만들 수 없어요")
    return OpenAI(api_key=settings.openai_api_key)


def _json_chat(system: str, user: str, temperature: float, model: str | None = None) -> dict:
    resp = _client().chat.completions.create(
        model=model or settings.openai_model,
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


def _prod_lines(prods: list[dict]) -> list[str]:
    return [
        f"- {p.get('name')} {p.get('qty') or ''} ({p.get('date') or ''} {p.get('time') or ''}"
        + (f", 매진 {p['sold_out']}" if p.get("sold_out") else "") + ")"
        for p in prods
    ] or ["- (기록 없음)"]


def concept_of(ad: dict) -> str:
    """화면에서 고른 광고 느낌. 선택지 밖(빈 값·옛 데이터)이면 유쾌함 — 밈 기반 광고의 기본값."""
    c = str(ad.get("ad_concept") or "").strip()
    return c if c in CONCEPT_RECIPES else "유쾌함"


def caption_of(store: dict) -> str:
    """그림 아래 캡션 — 가게 정보는 대사가 아니라 여기로. 비어 있는 칸은 건너뛴다."""
    parts = [store.get("desc"), store.get("hours"), store.get("address")]
    return " · ".join(str(p).strip() for p in parts if p and str(p).strip())


def script_user_message(card: dict, meme_title: str, store: dict, prods: list[dict], ad: dict, character: dict) -> str:
    """작가 GPT에 보내는 것. 마스코트 시트(성격·나이·취미·능력·키워드)를 통째로 준다 — 말투의 재료."""
    concept = concept_of(ad)
    ch = {k: v for k, v in character.items() if v}
    return (
        f"[밈 카드: {meme_title}]\n{json.dumps(card, ensure_ascii=False, indent=1)}\n\n"
        f"[광고 느낌] {concept}\n레시피: {CONCEPT_RECIPES[concept]}\n\n"
        f"[가게]\n업종: {store.get('category') or '빵집'}\n소개: {store.get('desc') or ''}\n"
        f"[생산 기록]\n" + "\n".join(_prod_lines(prods)) + "\n\n"
        f"[마스코트 시트]\n{json.dumps(ch, ensure_ascii=False, indent=1)}"
    )


def direct_user_message(script: dict, ad: dict) -> str:
    concept = concept_of(ad)
    return (f"[광고 느낌] {concept}\n레시피: {CONCEPT_RECIPES[concept]}\n\n"
            f"[작가가 고른 대본]\n{json.dumps({'title': script['title'], 'lines': script['lines'], 'beats': script['beats']}, ensure_ascii=False, indent=1)}")


def _pick(val, choices, default):
    v = str(val or "").strip()
    return v if v in choices else default


def propose_story(card: dict, meme_title: str, store: dict, prods: list[dict], ad: dict, character: dict | str) -> dict:
    """카드 + 가게 + 느낌 + 마스코트 시트 → {title, cuts[4], caption, fit, drafts, best, why, concept}.

    두 단계: 작가(대사 3편 → 하나 고름, temperature 0.9) → 연출(고른 대사를 슬롯으로, 0.3).
    character 는 시트 dict. 옛 호출처럼 이름 문자열만 오면 이름만 쓴다."""
    if isinstance(character, str):
        character = {"name": character}
    concept = concept_of(ad)

    # 1) 작가
    s_user = script_user_message(card, meme_title, store, prods, ad, character)
    sdata = _json_chat(_SCRIPT_PROMPT, s_user, temperature=0.9, model=settings.openai_writer_model)
    drafts = [d for d in (sdata.get("drafts") or []) if isinstance(d, dict) and isinstance(d.get("lines"), list)]
    if not drafts:
        raise RuntimeError("스토리 형식이 어긋났어요 — 다시 제안받아 주세요")
    try:
        best = int(sdata.get("best", 0))
    except (TypeError, ValueError):
        best = 0
    best = best if 0 <= best < len(drafts) else 0
    chosen = drafts[best]
    lines = [str(x or "").strip() for x in chosen["lines"]][:4]
    beats = [str(x or "").strip() for x in (chosen.get("beats") or [])][:4]
    while len(lines) < 4:
        lines.append("")
    while len(beats) < 4:
        beats.append("")
    script = {"title": str(chosen.get("title") or meme_title), "lines": lines, "beats": beats,
              "voice": str(chosen.get("voice") or "")}
    if sum(1 for x in lines if x) < 2:
        raise RuntimeError("스토리 형식이 어긋났어요 — 다시 제안받아 주세요")

    # 2) 연출
    d_user = direct_user_message(script, ad)
    ddata = _json_chat(_DIRECT_PROMPT, d_user, temperature=0.3)
    raw_cuts = list(ddata.get("cuts") or [])
    cuts = []
    for i in range(4):
        c = raw_cuts[i] if i < len(raw_cuts) and isinstance(raw_cuts[i], dict) else {}
        shot = c.get("shot") if isinstance(c.get("shot"), dict) else {}
        props = c.get("props") or []
        line = lines[i]
        cuts.append({
            "n": i + 1,
            "line": line,
            "action": beats[i],   # 화면 표시용 한 줄 요약(작가의 beat)
            "short": line[:14],
            "caption": caption_of(store),   # 그림 아래 캡션 — 가게 정보는 대사가 아니라 여기로
            "slots": {
                "shot": {
                    "size": _pick(shot.get("size"), SHOT_SIZE_CHOICES, "작게"),
                    "angle": _pick(shot.get("angle"), SHOT_ANGLE_CHOICES, "정면"),
                    "count": _pick(shot.get("count"), SHOT_COUNT_CHOICES, "혼자"),
                    # 대사 있는 컷의 기본은 홀수 오른쪽·짝수 왼쪽(말풍선 반대편), 대사 없으면 가운데
                    "position": _pick(shot.get("position"), SHOT_POSITION_CHOICES,
                                      "가운데" if not line else ("오른쪽" if i % 2 == 0 else "왼쪽")),
                },
                "gaze": _pick(c.get("gaze"), GAZE_CHOICES, "옆"),
                "expression": str(c.get("expression") or "").strip(),
                "pose": str(c.get("pose") or "").strip(),
                "place": str(c.get("place") or "").strip(),
                "props": [str(p) for p in props] if isinstance(props, list) else [str(props)],
                "light": str(c.get("light") or "").strip(),
            },
        })
    return {"title": script["title"], "cuts": cuts, "caption": caption_of(store), "concept": concept,
            "fit": sdata.get("fit") or {}, "drafts": drafts, "best": best, "why": str(sdata.get("why") or ""),
            "voice": script["voice"], "script_user": s_user, "direct_user": d_user}
