"""캐릭터 시트 — 무엇을 묻고, 언제 다 찼고, 무엇으로 그림을 그리는가.

규칙(기획 화이트보드 기준):

1. 시트가 **전부** 채워지지 않으면 후보를 생성하지 않는다. 다 찼다는 사실은 알려준다.
2. 후보 생성은 사장님이 버튼을 눌러야만 시작된다 — 대화 도중에 저절로 돌지 않는다.
3. 이미지 태깅에 쓰는 건 **외형 + 아웃핏 + 나이** 세 칸뿐이다.
4. 대화 가이드 순서는 외형 → 아웃핏 → 설명 → 능력 → 나이 → 성별 → 이름.
5. 퍼스널 키워드는 묻지 않는다. 마지막에 자동으로 뽑아 "이렇게 정했다"고 제안한다.
6. 시트가 다 찬 뒤의 수정은 즉시 반영하지 않는다. 전/후를 보여주고 승인을 받는다.
7. 수정을 반영한 뒤에는 가이드 순서상 다음 칸도 고칠지 물어본다. 사장님은 그 제안을
   무시하고 아무 칸이나 골라 고쳐도 된다.

여기에 LLM은 없다. 이 저장소의 채팅은 전부 규칙 기반이고(services/chat_ai.py),
그래서 대화는 **한 번에 한 칸씩 묻고 답을 그 칸에 그대로 넣는** 방식이다. 지어내지
않으므로 사장님이 쓴 말이 그대로 시트에 남는다. LLM을 붙인다면 갈아끼울 자리는
`absorb()` 하나다 — 한 문장에서 여러 칸을 채우는 일만 그쪽으로 넘기면 된다.
"""

import re

# (필드, 라벨, 사장님에게 묻는 말)
# 순서가 곧 가이드 순서다. 화면도 이 순서로 시트를 그린다.
FIELDS: list[tuple[str, str, str]] = [
    ("look", "외형",
     "어떻게 생긴 캐릭터였으면 좋겠어요? 종류·몸집·색·눈매처럼 눈에 보이는 걸 적어주세요."),
    # 앞치마·조끼처럼 겉에 걸치는 것만 적히면 그림 모델이 속에 입을 옷을 지어낸다.
    # 그건 사장님이 정한 적 없는 옷이므로, 물어볼 때 **안에 뭘 입을지도 같이** 묻는다.
    # "그냥 털 위에"도 답이라는 걸 알려줘야 한다 — 그게 마스코트에선 흔한 모습이다.
    ("outfit", "아웃핏",
     "무엇을 입고 있으면 좋을까요? 옷이나 앞치마, 모자 같은 걸 적어주세요. "
     "앞치마처럼 겉에 걸치는 것만 있으면 안에 뭘 입을지도 알려주세요 — "
     "'그냥 털 위에 앞치마만'도 좋아요."),
    ("desc", "설명",
     "이 캐릭터를 한두 문장으로 소개해 주세요. 어떤 성격이고, 가게에서 무슨 역할인가요?"),
    ("abilities", "능력",
     "잘하는 일이나 특기가 있나요? 광고에서 이 캐릭터가 뭘 해내면 좋을지로 생각하셔도 돼요."),
    ("age", "나이",
     "나이는 어느 정도로 볼까요? '3살'처럼 숫자로도 좋고 '어린', '나이 든'처럼 느낌으로도 돼요."),
    ("gender", "성별",
     "성별은 어떻게 할까요? 정하지 않아도 되면 '없음'이라고 적어주세요."),
    ("name", "이름",
     "마지막이에요. 이 캐릭터를 뭐라고 부를까요?"),
]

ORDER = [f for f, _, _ in FIELDS]
LABELS = {f: label for f, label, _ in FIELDS}
QUESTIONS = {f: q for f, _, q in FIELDS}

# 묻지 않고 자동으로 채우는 칸.
KEYWORDS_FIELD = "keywords"
KEYWORDS_LABEL = "퍼스널 키워드"

# 이미지 태깅에 들어가는 칸. 순서가 곧 태그 프롬프트에 적히는 순서다.
#
# 사장님이 적은 것이 그림까지 최대한 가야 한다. 그래서 겉모습뿐 아니라 성격·능력·
# 키워드도 넘긴다 — 성격과 키워드는 표정 태그로, 능력은 손에 든 소품 태그로 바뀐다
# (chat_ai._IMAGE_LABEL이 칸마다 무엇으로 바꿀지 알려준다).
#
# **이름은 넘기지 않는다.** "구웅이"에 대응하는 Danbooru 태그는 없고, 태그 변환기에
# 들어가면 그림과 무관한 잡음이 하나 더 붙을 뿐이다. 성별도 넘기지 않는다 — 동물
# 마스코트에서 성별 태그(1boy/1girl)는 사람 몸을 끌어와 치비 동물 그림을 망가뜨린다.
IMAGE_FIELDS = ["look", "outfit", "age", "desc", "abilities", KEYWORDS_FIELD]

MAX_KEYWORDS = 5


def value_of(char, field: str) -> str:
    """시트 한 칸의 값을 문자열로. 키워드는 리스트라 쉼표로 이어 붙인다."""
    if field == KEYWORDS_FIELD:
        return ", ".join(char.keywords or [])
    return (getattr(char, field, "") or "").strip()


def missing_fields(char) -> list[str]:
    """아직 비어 있는 칸. 가이드 순서 그대로 돌려준다."""
    return [f for f in ORDER if not value_of(char, f)]


def is_complete(char) -> bool:
    """**묻는** 칸이 전부 찼는가. 대화를 계속할지 말지를 이걸로 정한다.

    키워드는 빼고 센다 — 묻지 않고 자동으로 뽑는 칸이라, 여기 넣으면 가이드가
    사장님에게 키워드를 물어보게 된다.
    """
    return not missing_fields(char)


def missing_all(char) -> list[str]:
    """비어 있는 칸 전부. 자동으로 채우는 키워드까지 포함한다."""
    remaining = missing_fields(char)
    if not value_of(char, KEYWORDS_FIELD):
        remaining.append(KEYWORDS_FIELD)
    return remaining


def ready_to_generate(char) -> bool:
    """후보 생성을 열어도 되는가 — 시트가 **전부** 찼을 때만이다.

    묻는 칸 7개에 더해 퍼스널 키워드까지 본다. 키워드는 자동 제안이지만 사장님이
    승인하거나 직접 적어야 채워진다. 즉 사장님이 시트 전체를 한 번은 확인한 뒤에야
    그림이 돌아간다.
    """
    return not missing_all(char)


def next_field(char) -> str:
    """다음에 물어볼 칸. 다 찼으면 빈 문자열."""
    remaining = missing_fields(char)
    return remaining[0] if remaining else ""


def next_in_guide(field: str) -> str:
    """가이드 순서상 이 칸 다음 칸. 마지막이면 빈 문자열."""
    if field not in ORDER:
        return ""
    position = ORDER.index(field) + 1
    return ORDER[position] if position < len(ORDER) else ""


def sheet_rows(char) -> list[dict]:
    """화면에 그릴 시트. 값이 없는 칸은 빈 문자열로 — 예시 문구로 메우지 않는다."""
    rows = [
        {"field": f, "label": LABELS[f], "value": value_of(char, f), "auto": False}
        for f in ORDER
    ]
    rows.append({
        "field": KEYWORDS_FIELD,
        "label": KEYWORDS_LABEL,
        "value": value_of(char, KEYWORDS_FIELD),
        "auto": True,
    })
    return rows


# ---------------------------------------------------------------- 퍼스널 키워드

# 퍼스널 키워드는 성격을 나타내는 말, 곧 **형용사**다. 그래서 명사는 건드리지 않고
# 사장님이 쓴 형용사만 골라낸다. 한국어 형태소 분석기 없이 명사까지 노리면
# '역할이에요'가 '역할이에'로, '느긋하고'가 '느긋'으로 잘려 나온다 — 그런 조각을
# 사장님 캐릭터의 성격이라고 내놓을 수는 없다.
#
# 이미 관형형인 말은 그대로 쓴다: 다정한 · 통통한 · 동그란 · 차분한
_ADJ_TAIL_RE = re.compile(r"^.{2,6}(?:한|운|란|던)$")
# 연결형은 관형형으로 되돌린다: 느긋하고 → 느긋한 · 사랑스럽고 → 사랑스러운
_ADJ_FORMS = [
    (re.compile(r"^(.{1,6}?)(?:하고|하며|했고|하지만|하지|해서)$"), "한"),
    (re.compile(r"^(.{1,6}?)(?:스럽고|스럽다|스러운|스러워)$"), "스러운"),
    (re.compile(r"^(.{1,6}?)(?:롭고|롭다|로운|로워)$"), "로운"),
]

# 형용사 모양이지만 성격이 아닌 말. 이게 올라가면 '있는'이 캐릭터의 성격이 된다.
_STOP = {
    "있는", "없는", "하는", "되는", "같은", "이런", "저런", "그런", "어떤", "무슨",
    "다른", "여러", "많은", "적은", "좋은", "이라는", "라는", "대한", "위한", "관한",
}


def _as_adjective(word: str) -> str:
    """낱말이 형용사면 관형형으로 돌려주고, 아니면 빈 문자열."""
    for pattern, tail in _ADJ_FORMS:
        match = pattern.match(word)
        if match and len(match.group(1)) >= 2:
            return match.group(1) + tail
    if _ADJ_TAIL_RE.match(word):
        return word
    return ""


def derive_keywords(char, limit: int = MAX_KEYWORDS) -> list[str]:
    """사장님이 쓴 문장에서 성격 키워드를 뽑는다. **없는 말을 지어내지 않는다.**

    설명 → 능력 → 외형 순으로 훑는다. 성격을 가장 잘 담은 칸이 설명이라서다.

    뽑을 게 없으면 빈 리스트를 돌려준다. 그때는 라우터가 사장님에게 직접 물어본다 —
    그럴듯한 단어를 채워 넣으면 그건 사장님이 정한 적 없는 캐릭터 성격이 된다.
    """
    picked: list[str] = []
    seen: set[str] = set()

    for field in ("desc", "abilities", "look"):
        for raw in re.split(r"[^\w가-힣]+", value_of(char, field)):
            if not raw or raw.isdigit():
                continue
            word = _as_adjective(raw)
            if not word or word in _STOP or word in seen:
                continue
            seen.add(word)
            picked.append(word)
            if len(picked) >= limit:
                return picked
    return picked


# ---------------------------------------------------------------- 대화 흡수

def absorb(char, field: str, text: str) -> str:
    """사장님이 쓴 문장을 해당 칸에 넣는다. 넣은 값을 돌려준다.

    한 칸을 물었으면 그 답을 그대로 넣는다 — 말을 다듬거나 요약하지 않는다.
    LLM을 붙인다면 갈아끼울 자리가 여기다(한 문장에서 여러 칸을 채우는 일).
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    if field == KEYWORDS_FIELD:
        parts = [p.strip() for p in re.split(r"[,、·/]| 그리고 ", cleaned) if p.strip()]
        char.keywords = parts[:MAX_KEYWORDS]
        return ", ".join(char.keywords)
    setattr(char, field, cleaned)
    return cleaned


def diff_for(char, field: str, new_value: str) -> list[dict]:
    """수정 전/후 한 줄. 화면의 confirm 카드가 이대로 그린다."""
    before = value_of(char, field)
    return [{
        "label": LABELS.get(field, KEYWORDS_LABEL),
        "from": before or "아직 없음",
        "to": new_value or "비움",
    }]
