# 파일명: classify_memes_situation.py
#
# [전체 동작 과정]
# 1. memes 테이블(app.db)에서 밈을 읽는다
# 2. situation_categories(상황 카테고리)의 "예시 문장들"을 임베딩 모델로 벡터화하고,
#    카테고리별로 평균 벡터를 만든다
# 3. 밈들의 classification_text(이름 + 유래 앞 2문장 + 활용예시)도 벡터화한다
# 4. 코사인 유사도로 가장 가까운 카테고리를 찾는다
# 5. 유사도가 너무 낮으면 "미분류" 처리한다
# 6. 1위와 2위 카테고리 점수 차이(margin)를 보고 "확신도"(낮음/보통/높음)를 매긴다
#    → margin이 거의 0에 가까운 경우(사실상 랜덤 수준)는 결과를 그대로 믿으면 안 되므로
#      "situation_confidence" 필드로 표시해서, 나중에 사람이 우선적으로 검수하게 한다
#    (주의: 이 필드는 상황 카테고리를 강제로 "미분류"로 바꾸는 게 아니라,
#     "이 결과를 얼마나 믿어도 되는지"를 별도로 알려주는 용도다. margin이 낮다고
#     무조건 미분류로 바꾸면, 실제로는 맞게 분류된 애매한 케이스까지 함께 버려지기 때문이다.)
# 7. [진단용] 카테고리별로 "전체 밈과의 평균 유사도"를 출력한다
#    → 특정 카테고리(예: 불만_토로)가 애매한 경우에 자꾸 근소하게 이기는 게,
#      혹시 그 카테고리 벡터가 임베딩 공간에서 유독 "중간적인" 위치에 있어서는
#      아닌지 확인하기 위한 코드다.
# 8. 결과를 csv, json으로 저장한다 (DB에 다시 넣는 건 여전히 import_memes.py 몫이다)

import csv
import json
import math
import os
import re
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# -----------------------------
# 0. 설정값
# -----------------------------
# VM 운영 경로를 기본값으로 고정한다 — 다른 위치(예: ~/test)에서 테스트할 땐
# MEME_CLASSIFY_DB 환경변수로 경로를 바꿔주면 된다.
DB_PATH = os.environ.get("MEME_CLASSIFY_DB", "/home/sprint05/part4_3team/backend/app.db")
OUTPUT_JSON_PATH = "memes_classified.json"
OUTPUT_CSV_PATH = "memes_classified.csv"

# text-embedding-3-small 기준 임계값 — 이전에 쓰던 sentence-transformers 모델과
# 코사인 유사도 값의 분포 자체가 다르다(임베딩 모델이 바뀌면 값 범위도 달라진다).
# MEME_CLASSIFY_THRESHOLD 환경변수로 코드를 안 건드리고 바꿀 수 있다.
SIMILARITY_THRESHOLD = float(os.environ.get("MEME_CLASSIFY_THRESHOLD", "0.228"))

# [바뀐 점] margin(1위-2위 점수 차이) 기준을 하나가 아니라 두 개로 나눴다.
# 실제 결과 데이터를 분석해보니:
#   - margin < 0.01: 1위/2위가 사실상 동점 → "낮음" (믿으면 안 됨. 실제로 이 구간에서
#     장원영 OO, 모르는개산책이 불만_토로로 잘못 분류되는 걸 확인했다)
#   - 0.01 <= margin < 0.05: 약한 확신 → "보통"
#   - margin >= 0.05: 비교적 뚜렷한 1위 → "높음"
# 이 값들도 데이터를 더 보면서 조정할 수 있도록 환경변수로 뺐다.
MARGIN_LOW_THRESHOLD = float(os.environ.get("MEME_CLASSIFY_MARGIN_LOW", "0.01"))
MARGIN_MID_THRESHOLD = float(os.environ.get("MEME_CLASSIFY_MARGIN_MID", "0.05"))

# text-embedding-3-small(기본) 또는 text-embedding-3-large. 다른 임베딩 모델로
# 테스트해볼 때 코드를 안 건드리고 바꿀 수 있게 환경변수로 뺐다.
MODEL_NAME = os.environ.get("MEME_CLASSIFY_MODEL", "text-embedding-3-small")

# -----------------------------
# 1. 상황(시나리오) 카테고리 정의
# -----------------------------
# "설명"은 사람이 읽기 위한 문서용 텍스트, "예시문장"은 실제 임베딩에 쓰이는 텍스트다.
#
# [바뀐 점] 재미_밈놀이에 예시문장을 계속 보강하는 중이다.
# 1차로 "기존 단어/속담을 비틀어서 새 유행어를 만드는 말장난" 문장 2개를 추가해서
# 모르는개산책, 삐에로 밈은 고쳐졌다. 하지만 아래 두 유형은 여전히 놓치고 있었다.
#
#   (a) 장원영 OO 유형 — "고유명사(인물/캐릭터 이름)를 다른 단어 뒤에 붙여서
#       긍정적인 감정을 과장해서 강조하는" 패턴. 기존 예시문장 중
#       "특정 단어나 표현을 다른 것에 붙여서 따라 하는 놀이"가 있긴 했지만
#       너무 일반적인 문장이라 "긍정 감정 강조"라는 핵심 뉘앙스를 못 담았다.
#       그래서 여전히 불만_토로와 근소한 차이(margin 0.006)로 헷갈렸다.
#
#   (b) 고맙투우사 챌린지 유형 — "발음이 비슷한 단어로 바꾸는 말장난 + 그에 맞는
#       우스꽝스러운 동작/퍼포먼스가 결합된 챌린지" 패턴. 1차 보강 때 넣은
#       "속담 비틀기" 문장과는 결이 달라서(속담이 아니라 순수 언어유희+몸개그),
#       오히려 재미_밈놀이 벡터가 속담 비틀기 쪽으로 쏠리면서 이 밈이 상대적으로
#       멀어져 전후_비교로 잘못 넘어가는 부작용이 생겼다.
#
# → (a), (b) 패턴을 각각 정확히 겨냥한 예시문장을 추가로 넣는다.
situation_categories = {
    "반응_기다림": {
        "설명": """
        상대방의 답장, 연락, 반응 또는 결과를 기다리는 상황.
        답이 오지 않거나 결과를 기다리면서 궁금해하거나 초조해하거나
        투정하는 상황이 핵심이다.
        """,
        "예시문장": [
            "답장이 오기를 초조하게 기다리는 상황",
            "연락이 안 와서 계속 확인하게 되는 상황",
            "결과가 궁금해서 애타게 기다리는 상황",
        ],
        "광고적합": True,
    },
    "전후_비교": {
        "설명": """
        어떤 행동이나 사건을 기준으로 이전과 이후의 상태가 달라지는
        모습을 비교해서 보여주는 상황.
        비포와 애프터처럼 변화 전후를 대비하는 것이 핵심이다.
        """,
        "예시문장": [
            "행동 전과 후의 달라진 모습을 비교해서 보여주는 상황",
            "비포 애프터처럼 변화를 대비해서 보여주는 상황",
            "어떤 계기로 확 달라진 결과를 보여주는 상황",
        ],
        "광고적합": True,
    },
    "신규_시작": {
        "설명": """
        새로운 제품, 서비스, 활동 또는 도전을 처음 시작하거나
        출시하는 상황.
        새로운 것을 시작한다는 의미가 핵심이다.
        """,
        "예시문장": [
            "새로운 제품이나 서비스를 처음 시작하는 상황",
            "새로운 도전이나 활동을 막 시작하는 상황",
            "처음 출시하거나 오픈하는 상황",
        ],
        "광고적합": True,
    },
    "감탄_긍정반응": {
        "설명": """
        사람, 제품, 음식, 결과 또는 상황이 마음에 들거나 좋아서
        감탄하거나 칭찬하거나 긍정적인 반응을 표현하는 상황.
        좋다, 최고다, 마음에 든다 등의 긍정적인 반응이 핵심이다.
        단순히 재미있는 말장난이나 패러디, 챌린지는 포함하지 않는다.
        """,
        "예시문장": [
            "결과나 제품이 마음에 들어서 감탄하는 상황",
            "좋다, 최고다라며 칭찬하는 상황",
            "만족스러워서 긍정적으로 반응하는 상황",
        ],
        "광고적합": True,
    },
    "재미_밈놀이": {
        "설명": """
        특정 단어, 숫자, 문장, 소리, 행동 등을 다른 대상에 붙이거나
        변형하거나 반복해서 재미를 만드는 상황.
        언어유희, 말장난, 패러디, 드립, 챌린지, 따라 하기,
        참여형 놀이 등을 포함한다.
        상대방을 일부러 킹받게 하거나 놀리는 장난도 포함한다.
        실제로 불편함이나 부당함에 대해 불만을 표현하는 것이 목적이라면
        포함하지 않는다.
        """,
        "예시문장": [
            "특정 단어나 표현을 다른 것에 붙여서 따라 하는 놀이",
            "말장난이나 패러디로 웃음을 주는 상황",
            "유행하는 표현을 반복하며 참여하는 챌린지",
            "친구를 장난스럽게 놀리거나 킹받게 하는 드립",
            "기존 표현이나 속담을 살짝 비틀어서 새로운 유행어를 만드는 말장난",
            "특정 대상에 재미있는 별명을 붙이거나 이름을 변형해서 부르는 놀이",
            # (a) 장원영 OO 유형: 고유명사(인물/캐릭터 이름)를 다른 단어 뒤에 붙여서
            # 긍정적인 감정이나 상태를 과장해서 표현하는 패턴을 정확히 겨냥한 문장.
            "유명인이나 캐릭터의 이름을 다른 단어에 붙여서 기분이 좋거나 최고라는 걸 과장해서 표현하는 유행어",
            # (b) 고맙투우사 챌린지 유형: 발음이 비슷한 단어로 바꾸는 말장난에
            # 우스꽝스러운 동작이나 퍼포먼스가 결합된 챌린지 패턴을 겨냥한 문장.
            "발음이 비슷한 다른 단어로 바꾸는 말장난에 우스꽝스러운 동작이나 퍼포먼스를 결합한 챌린지",
        ],
        "광고적합": True,
    },
    "불만_토로": {
        "설명": """
        실제로 겪은 불편함, 답답함, 힘든 상황, 부당함 등에 대해
        자신의 불만을 표현하거나 하소연하거나 투정하는 상황.
        단순히 재미를 위해 '킹받게 한다', '열받게 한다'고 표현하거나
        상대방을 놀리는 드립은 포함하지 않는다.
        """,
        "예시문장": [
            "실제로 겪은 불편함이나 답답함을 하소연하는 상황",
            "부당한 일을 겪고 불만을 표현하는 상황",
            "힘든 상황에 대해 투정 부리는 상황",
        ],
        "광고적합": False,
    },
}


def get_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY가 비어 있어요 — 환경변수로 넣어주세요.")
        sys.exit(1)
    return OpenAI(api_key=api_key)


def embed(client: OpenAI, texts: list[str]) -> list[list[float]]:
    """문장 리스트를 OpenAI 임베딩 API로 한 번에 벡터화한다(반복 호출보다 효율적).
    응답의 data는 입력 순서대로 오지만, index로 한 번 더 맞춰서 순서를 보장한다."""
    resp = client.embeddings.create(model=MODEL_NAME, input=texts)
    rows = sorted(resp.data, key=lambda d: d.index)
    return [row.embedding for row in rows]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def average_vector(vectors: list[list[float]]) -> list[float]:
    """여러 개의 벡터를 받아서 각 차원별 평균을 낸 벡터 하나를 반환하는 함수.
    카테고리를 예시 문장 여러 개로 표현하기로 했기 때문에, 그 문장들을 각각
    임베딩한 뒤 평균을 내서 "카테고리를 대표하는 벡터"를 만든다."""
    dim = len(vectors[0])
    total = [0.0] * dim
    for vec in vectors:
        for i in range(dim):
            total[i] += vec[i]
    return [x / len(vectors) for x in total]


def get_origin_first_sentences(origin: str, max_sentences: int = 2, max_len: int = 150) -> str:
    """origin(밈의 유래) 텍스트에서 앞쪽 몇 문장만 뽑아내는 함수.

    [버그 수정] 이전 버전은 문장 구분 기준에 줄바꿈(\\n)도 포함시켰다.
    그런데 origin 텍스트 중에는 문장 하나를 여러 줄에 걸쳐 쓰는 스타일이 있어서,
    이런 경우 진짜 문장이 끝나기도 전에 줄바꿈에서 잘려버리는 문제가 있었다.
    실제로 '장원영 OO' 밈에서 origin이
        "작년에 붐업되었다가,\\n지금은 거의 일상어가 된 말이 있다면\\n..."
    처럼 줄바꿈으로 나뉘어 있었는데, 이전 함수는 첫 줄바꿈에서 바로 잘라서
    "작년에 붐업되었다가," 라는 의미 없는 조각만 남기고, 정작 핵심 정보인
    "좋으면 장원영을 외친다"는 내용은 통째로 날아갔다.
    → 문장 구분 기준에서 줄바꿈은 빼고 마침표(.)/느낌표(!)/물음표(?)만 쓴다.
      대신 줄바꿈 자체는 공백으로 바꿔서, 여러 줄에 걸친 문장이 안 끊기고
      하나로 이어지게 만든다.

    [문장 개수 확장] 이전 버전은 "첫 문장만" 가져왔는데, '고맙투우사 챌린지'처럼
    핵심 설명(말장난이 어떻게 만들어졌는지)이 두 번째 문장에 있는 경우 정보가
    부족했다. → 기본으로 앞에서 2문장까지 가져오도록 늘렸다.
    (그래도 너무 길어지는 건 막아야 하므로 max_len으로 전체 길이를 제한한다.)
    """
    if not origin:
        return ""

    # 줄바꿈을 공백으로 바꿔서, 한 문장이 여러 줄에 걸쳐 있어도 끊기지 않게 한다.
    normalized = origin.replace("\n", " ")

    # 마침표/느낌표/물음표가 나오는 위치(그 뒤끝)를 순서대로 모두 찾는다.
    sentence_ends = [m.end() for m in re.finditer(r"[.!?]", normalized)]

    if not sentence_ends:
        # 문장 구분자가 아예 없으면 텍스트 전체를 사용한다 (뒤에서 max_len으로 자름).
        result = normalized
    else:
        # 앞에서부터 max_sentences번째 구분자까지만 사용한다.
        cutoff_index = min(max_sentences, len(sentence_ends)) - 1
        result = normalized[: sentence_ends[cutoff_index]]

    # 문장 사이에 공백이 여러 개 남을 수 있으니 하나로 정리한다.
    result = re.sub(r"\s+", " ", result).strip()
    return result[:max_len]


def get_confidence_label(margin: float) -> str:
    """margin(1위-2위 점수 차이) 값을 보고 이 분류 결과를 얼마나 믿을 수 있는지
    "낮음" / "보통" / "높음" 세 단계로 나누는 함수.

    [왜 필요한가]
    실제 분류 결과를 검토해보니, margin이 0.002 수준으로 거의 0에 가까울 때
    (1위와 2위가 사실상 동점일 때) 엉뚱한 카테고리가 근소한 차이로 1위를 차지하는
    사례가 있었다 (예: 긍정적인 밈이 근소한 차이로 '불만_토로'가 되어버림).
    이런 경우를 상황 카테고리 자체를 강제로 바꾸기보다는, "이 결과는 신뢰도가
    낮으니 사람이 한 번 더 확인하라"는 신호로 남겨두는 게 더 안전하다.
    (강제로 미분류 처리하면, 실제로는 맞게 분류된 애매한 케이스까지 함께
    버려질 수 있기 때문이다 — 예: margin이 작아도 맞게 분류된 '고맙투우사 챌린지'
    같은 사례가 있었다.)
    """
    if margin < MARGIN_LOW_THRESHOLD:
        return "낮음"
    elif margin < MARGIN_MID_THRESHOLD:
        return "보통"
    else:
        return "높음"


def load_memes(db_path):
    """memes 테이블에서 밈을 읽어 분류에 필요한 모양으로 바꾸는 함수.
    classification_text는 "밈 이름 + 유래 앞 2문장 + 활용예시"를 이어붙여 만든다."""
    if not Path(db_path).exists():
        print(f"DB 파일을 못 찾았어요: {db_path}")
        print("MEME_CLASSIFY_DB 환경변수로 app.db 경로를 알려주세요.")
        sys.exit(1)

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT id, source, meme_name, origin, usage_example FROM memes"
        ).fetchall()
    finally:
        con.close()

    memes = []
    for r in rows:
        meme_name = r["meme_name"] or ""
        origin = r["origin"] or ""
        usage_example = r["usage_example"] or ""

        origin_summary = get_origin_first_sentences(origin)
        classification_text = "\n".join(
            t for t in (meme_name, origin_summary, usage_example) if t
        )

        memes.append({
            "id": r["id"],
            "source": r["source"] or "",
            "meme_name": meme_name,
            "origin": origin,
            "usage_example": usage_example,
            "classification_text": classification_text,
        })
    return memes


def get_category_vectors(client: OpenAI):
    """situation_categories의 "예시문장"들을 임베딩하고, 카테고리마다
    평균 벡터 하나씩을 만들어 반환하는 함수."""
    category_names = list(situation_categories.keys())

    all_sentences: list[str] = []
    sentence_counts: list[int] = []
    for name in category_names:
        sentences = situation_categories[name]["예시문장"]
        all_sentences.extend(sentences)
        sentence_counts.append(len(sentences))

    all_vectors = embed(client, all_sentences)

    category_vectors = []
    start = 0
    for count in sentence_counts:
        group = all_vectors[start:start + count]
        category_vectors.append(average_vector(group))
        start += count

    return category_names, category_vectors


def print_category_score_stats(meme_vectors, category_names, category_vectors):
    """[진단용] 각 카테고리가 "전체 밈"과 평균적으로 얼마나 유사한지 보여주는 함수.

    [왜 필요한가]
    애매한 경우(margin이 거의 0) '불만_토로'가 자꾸 근소하게 이기는 패턴이
    관찰됐다. 혹시 '불만_토로' 카테고리 벡터가 임베딩 공간에서 다른 카테고리들
    보다 "중간적인" 위치에 있어서, 어떤 밈과 비교해도 어느 정도 유사도가
    나오는 건 아닌지 확인하기 위한 진단 코드다.
    특정 카테고리의 평균 유사도가 다른 카테고리보다 눈에 띄게 높다면,
    그 카테고리의 예시문장을 더 구체적으로(범위를 좁혀서) 다시 써야 한다는 신호다.
    """
    print("\n=== [진단] 카테고리별 평균 유사도 (전체 밈 기준) ===")
    for idx, name in enumerate(category_names):
        scores = [cosine_similarity(mv, category_vectors[idx]) for mv in meme_vectors]
        avg_score = sum(scores) / len(scores)
        print(f"- {name}: 평균 {avg_score:.3f} (최소 {min(scores):.3f} / 최대 {max(scores):.3f})")


def classify_all_memes(memes, client: OpenAI):
    """밈 리스트 전체를 situation_categories 중 가장 유사한 카테고리로 분류하는 함수"""
    category_names, category_vectors = get_category_vectors(client)

    meme_texts = [item["classification_text"] for item in memes]
    meme_vectors = embed(client, meme_texts)

    # [진단용] 카테고리별 전체 평균 유사도를 먼저 출력해둔다 (불만_토로 편향 가설 확인용)
    print_category_score_stats(meme_vectors, category_names, category_vectors)

    results = []
    for i, item in enumerate(memes):
        similarities = [cosine_similarity(meme_vectors[i], v) for v in category_vectors]

        ranked = sorted(zip(category_names, similarities), key=lambda x: x[1], reverse=True)
        best_category, best_score = ranked[0]
        runner_up_category, runner_up_score = ranked[1]
        margin = round(best_score - runner_up_score, 3)
        confidence = get_confidence_label(margin)

        if confidence == "낮음":
            print(
                f"[확신도 낮음 - 검수 필요] {item['meme_name']}: "
                f"1위 {best_category}({best_score:.3f}) vs "
                f"2위 {runner_up_category}({runner_up_score:.3f}), margin={margin:.3f}"
            )

        if best_score < SIMILARITY_THRESHOLD:
            item["situation"] = "미분류"
            item["situation_score"] = round(best_score, 3)
            item["ad_safe"] = None
        else:
            item["situation"] = best_category
            item["situation_score"] = round(best_score, 3)
            item["ad_safe"] = situation_categories[best_category]["광고적합"]

        item["situation_runner_up"] = runner_up_category
        item["situation_margin"] = margin
        # [추가된 필드] 이 분류 결과를 얼마나 믿을 수 있는지 (낮음/보통/높음).
        # "낮음"인 항목, 특히 ad_safe=False(광고 부적합)로 분류된 항목은
        # 실제로는 광고에 써도 되는 밈이 잘못 제외됐을 수 있으니 우선 검수 대상이다.
        item["situation_confidence"] = confidence

        results.append(item)

    return results


def save_results(results):
    """분류 결과를 json과 csv 두 가지 형태로 저장하는 함수"""
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "source", "meme_name", "situation", "situation_score",
            "situation_confidence", "situation_margin", "situation_runner_up",
            "ad_safe", "origin",
        ])
        for item in results:
            writer.writerow([
                item["source"], item["meme_name"], item["situation"],
                item["situation_score"], item["situation_confidence"],
                item["situation_margin"], item["situation_runner_up"],
                item["ad_safe"], item["origin"][:100],
            ])

    print(f"JSON 결과 저장: {OUTPUT_JSON_PATH}")
    print(f"CSV 결과 저장: {OUTPUT_CSV_PATH}")


def print_summary(results):
    """분류 결과를 카테고리별 + 확신도별로 요약해서 출력하는 함수"""
    from collections import Counter

    counter = Counter(item["situation"] for item in results)
    print("\n=== 상황 카테고리별 분류 결과 요약 ===")
    for category, count in counter.most_common():
        ad_safe = situation_categories.get(category, {}).get("광고적합", "-")
        print(f"- {category}: {count}개  (광고적합: {ad_safe})")

    # [추가된 부분] 확신도(낮음/보통/높음)별 개수도 함께 보여준다.
    # "낮음"이 많다는 건 이 배치에서 검수가 필요한 항목이 많다는 뜻이다.
    confidence_counter = Counter(item["situation_confidence"] for item in results)
    print("\n=== 분류 확신도 요약 ===")
    for label in ["낮음", "보통", "높음"]:
        count = confidence_counter.get(label, 0)
        print(f"- {label}: {count}개")

    low_confidence_items = [i for i in results if i["situation_confidence"] == "낮음"]
    if low_confidence_items:
        names = ", ".join(i["meme_name"] for i in low_confidence_items)
        print(f"\n[검수 우선순위] 확신도 낮음 항목: {names}")


def main():
    print(f"1) OpenAI 임베딩 클라이언트를 준비하는 중입니다... (모델: {MODEL_NAME})")
    client = get_client()

    print(f"2) memes 테이블에서 밈 데이터를 불러오는 중입니다... ({DB_PATH})")
    memes = load_memes(DB_PATH)
    print(f"   → 총 {len(memes)}개 밈 데이터 로드 완료")

    print("3) 상황 카테고리로 분류하는 중입니다...")
    results = classify_all_memes(memes, client)

    print("4) 결과를 저장하는 중입니다...")
    save_results(results)

    print_summary(results)


if __name__ == "__main__":
    main()
