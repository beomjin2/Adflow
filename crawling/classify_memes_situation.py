# 파일명: classify_memes_situation.py
#
# [전체 동작 과정]
# 1. memes 테이블(app.db)에서 밈을 읽는다
# 2. situation_categories(상황 카테고리 설명들)를 임베딩 모델로 벡터화한다
# 3. 밈들의 combined_text(이름+유래+활용예시)도 벡터화한다
# 4. 코사인 유사도로 가장 가까운 카테고리를 찾는다
# 5. 유사도가 너무 낮으면 "미분류" 처리한다
# 6. 결과를 csv, json으로 저장한다 (DB에 다시 넣는 건 여전히 import_memes.py 몫이다)

import csv
import json
import math
import os
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
# 처음 이 모델로 바꿨다면 몇 건 돌려서 situation_score 분포를 보고 다시 맞출 것 —
# MEME_CLASSIFY_THRESHOLD 환경변수로 코드를 안 건드리고 바꿀 수 있다.
SIMILARITY_THRESHOLD = float(os.environ.get("MEME_CLASSIFY_THRESHOLD", "0.228"))

# text-embedding-3-small(기본) 또는 text-embedding-3-large. 다른 임베딩 모델로
# 테스트해볼 때 코드를 안 건드리고 바꿀 수 있게 환경변수로 뺐다.
MODEL_NAME = os.environ.get("MEME_CLASSIFY_MODEL", "text-embedding-3-small")

# -----------------------------
# 1. 상황(시나리오) 카테고리 정의
# -----------------------------
situation_categories = {
    "반응_기다림": {
        "설명": "누군가의 답장이나 반응, 결과를 기다리는 상황. 궁금함과 초조함이 섞여 있음",
        "광고적합": True,
    },
    "전후_비교": {
        "설명": "어떤 일을 겪기 전과 후의 모습이나 상태가 달라진 것을 비교해서 보여주는 상황",
        "광고적합": True,
    },
    "신규_시작": {
        "설명": "새로운 것을 처음 시작하거나 출시하거나 도전하는 상황",
        "광고적합": True,
    },
    "감탄_긍정반응": {
        "설명": "무언가가 마음에 들거나 좋아서 감탄하고 칭찬하는 긍정적인 반응",
        "광고적합": True,
    },
    "재미_밈놀이": {
        "설명": "단어나 문구를 재미있게 바꾸거나 조합해서 노는 말장난, 챌린지 놀이",
        "광고적합": True,
    },
    "불만_토로": {
        "설명": "답답하거나 부당한 일, 힘든 상황에 대해 하소연하거나 투덜거리는 상황",
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


def load_memes(db_path):
    """memes 테이블에서 밈을 읽어 분류에 필요한 모양으로 바꾸는 함수.

    combined_text는 DB에 저장된 컬럼이 아니라 여기서 이름+유래+활용예시를 이어붙여
    만든다 — situation 임베딩과 비교할 문장이 필요해서다(빈 필드는 건너뛴다)."""
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
        combined_text = "\n".join(
            t for t in (r["meme_name"], r["origin"], r["usage_example"]) if t
        )
        memes.append({
            "id": r["id"],
            "source": r["source"] or "",
            "meme_name": r["meme_name"] or "",
            "origin": r["origin"] or "",
            "combined_text": combined_text,
        })
    return memes


def classify_all_memes(memes, client: OpenAI):
    """밈 리스트 전체를 situation_categories 중 가장 유사한 카테고리로 분류하는 함수"""
    category_names = list(situation_categories.keys())
    category_descriptions = [info["설명"] for info in situation_categories.values()]

    # 카테고리 설명들과 밈 텍스트들을 각각 한 번에 벡터화 (반복 호출보다 효율적)
    category_vectors = embed(client, category_descriptions)
    meme_texts = [item["combined_text"] for item in memes]
    meme_vectors = embed(client, meme_texts)

    results = []
    for i, item in enumerate(memes):
        similarities = [cosine_similarity(meme_vectors[i], v) for v in category_vectors]
        best_score = max(similarities)
        best_index = similarities.index(best_score)
        best_category = category_names[best_index]

        if best_score < SIMILARITY_THRESHOLD:
            item["situation"] = "미분류"
            item["situation_score"] = round(best_score, 3)
            item["ad_safe"] = None
        else:
            item["situation"] = best_category
            item["situation_score"] = round(best_score, 3)
            item["ad_safe"] = situation_categories[best_category]["광고적합"]

        results.append(item)

    return results


def save_results(results):
    """분류 결과를 json과 csv 두 가지 형태로 저장하는 함수"""
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "meme_name", "situation", "situation_score", "ad_safe", "origin"])
        for item in results:
            writer.writerow([
                item["source"], item["meme_name"], item["situation"],
                item["situation_score"], item["ad_safe"], item["origin"][:100],
            ])

    print(f"JSON 결과 저장: {OUTPUT_JSON_PATH}")
    print(f"CSV 결과 저장: {OUTPUT_CSV_PATH}")


def print_summary(results):
    """분류 결과를 카테고리별로 몇 개씩 나왔는지 요약해서 출력하는 함수"""
    from collections import Counter
    counter = Counter(item["situation"] for item in results)
    print("\n=== 상황 카테고리별 분류 결과 요약 ===")
    for category, count in counter.most_common():
        ad_safe = situation_categories.get(category, {}).get("광고적합", "-")
        print(f"- {category}: {count}개  (광고적합: {ad_safe})")


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
