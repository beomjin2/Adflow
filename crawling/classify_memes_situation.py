# 파일명: classify_memes_situation.py
# 실행 환경: GCP VM (리눅스) 전용 버전 - torch/sentence-transformers 사용
#
# [로컬 Windows 버전과 다른 점]
# 로컬 PC에서는 Windows 보안정책(스마트 앱 제어)이 torch DLL을 차단해서
# fastembed(다국어 모델)로 우회했었는데,
# 리눅스 기반 GCP VM에서는 이 문제가 없으므로
# 한국어에 더 특화된 sentence-transformers + ko-sroberta-multitask 모델을 사용합니다.
#
# [전체 동작 과정]
# 1. memes_normalized.json 파일을 읽는다
# 2. situation_categories(상황 카테고리 설명들)를 임베딩 모델로 벡터화한다
# 3. 밈들의 combined_text도 벡터화한다
# 4. 코사인 유사도로 가장 가까운 카테고리를 찾는다
# 5. 유사도가 너무 낮으면 "미분류" 처리한다
# 6. 결과를 csv, json으로 저장한다

import json
import csv
import os
from sentence_transformers import SentenceTransformer, util

# -----------------------------
# 0. 설정값
# -----------------------------
INPUT_PATH = "memes_normalized.json"
OUTPUT_JSON_PATH = "memes_classified.json"
OUTPUT_CSV_PATH = "memes_classified.csv"

# ko-sroberta-multitask 모델 기준 임계값 (fastembed/e5 모델과 값 범위가 다름)
SIMILARITY_THRESHOLD = 0.35

# 한국어 전용 문장 임베딩 모델. 다른 임베딩 모델로 테스트해볼 때 코드를 안 건드리고
# 바꿀 수 있게 환경변수로 뺐다 — 안 정해주면 지금 쓰는 모델이 기본값이다.
MODEL_NAME = os.environ.get("MEME_CLASSIFY_MODEL", "jhgan/ko-sroberta-multitask")

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


def load_memes(path):
    """정규화된 밈 데이터 JSON 파일을 읽어오는 함수"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def classify_all_memes(memes, model):
    """밈 리스트 전체를 situation_categories 중 가장 유사한 카테고리로 분류하는 함수"""
    category_names = list(situation_categories.keys())
    category_descriptions = [info["설명"] for info in situation_categories.values()]

    # 카테고리 설명들과 밈 텍스트들을 각각 한 번에 벡터화 (반복 호출보다 효율적)
    category_vectors = model.encode(category_descriptions)
    meme_texts = [item["combined_text"] for item in memes]
    meme_vectors = model.encode(meme_texts)

    results = []
    for i, item in enumerate(memes):
        similarities = util.cos_sim(meme_vectors[i], category_vectors)[0]
        best_index = similarities.argmax().item()
        best_score = similarities[best_index].item()
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
    print("1) 임베딩 모델을 불러오는 중입니다... (처음 실행 시 다운로드로 시간이 걸릴 수 있음)")
    model = SentenceTransformer(MODEL_NAME)

    print("2) 밈 데이터를 불러오는 중입니다...")
    memes = load_memes(INPUT_PATH)
    print(f"   → 총 {len(memes)}개 밈 데이터 로드 완료")

    print("3) 상황 카테고리로 분류하는 중입니다...")
    results = classify_all_memes(memes, model)

    print("4) 결과를 저장하는 중입니다...")
    save_results(results)

    print_summary(results)


if __name__ == "__main__":
    main()
