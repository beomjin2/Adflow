"""pipeline_dedupe.py — 사이트끼리 겹치는 같은 밈을 유래 텍스트 유사도로 묶는다.

규칙은 프로젝트 문서 「밈 크롤링 파싱 전략 정리」 6절 그대로(31건 → 25건, 정답 7쌍 전부·오탐 0으로 맞춘 값):
  1. 이름 유사도 ≥ 0.20 이고 유래 유사도 ≥ 0.05
  2. 유래 유사도 ≥ 0.17
  3. 서로의 이름이 상대 유래에 등장(앞뒤 부분일치 허용)하고 유래 유사도 ≥ 0.08
  · 같은 사이트끼리는 비교하지 않는다 · union-find로 전파 · 대표는 유래가 가장 짧은 것

TF-IDF는 scikit-learn의 TfidfVectorizer(analyzer="char_wb", ngram_range=(2,4), sublinear_tf=True)와
같은 계산을 표준 라이브러리로 옮겼다 — VM/크론 환경에 scikit-learn을 따로 깔지 않으려고.
(idf = ln((1+n)/(1+df)) + 1, tf = 1 + ln(tf), L2 정규화, char_wb는 단어 앞뒤에 공백을 붙여 자른다)
"""
from __future__ import annotations

import math
import re
from collections import Counter
from itertools import combinations

NAME_T, ORIGIN_LOW, ORIGIN_ONLY, MENTION_T = 0.20, 0.05, 0.17, 0.08


def _char_wb(text: str, lo: int = 2, hi: int = 4) -> list[str]:
    grams = []
    for w in re.sub(r"\s+", " ", (text or "").lower()).split():
        w = f" {w} "
        for n in range(lo, hi + 1):
            off = 0
            grams.append(w[off:off + n])
            while off + n < len(w):
                off += 1
                grams.append(w[off:off + n])
            if off == 0:
                break
    return grams


def tfidf_cosine(docs: list[str]) -> list[list[float]]:
    counts = [Counter(_char_wb(d)) for d in docs]
    n = len(docs)
    df = Counter(g for c in counts for g in c)
    idf = {g: math.log((1 + n) / (1 + d)) + 1 for g, d in df.items()}
    vecs = []
    for c in counts:
        v = {g: (1 + math.log(tf)) * idf[g] for g, tf in c.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({g: x / norm for g, x in v.items()})
    sim = [[0.0] * n for _ in range(n)]
    for i in range(n):
        sim[i][i] = 1.0
        for j in range(i + 1, n):
            a, b = (vecs[i], vecs[j]) if len(vecs[i]) < len(vecs[j]) else (vecs[j], vecs[i])
            s = sum(x * b.get(g, 0.0) for g, x in a.items())
            sim[i][j] = sim[j][i] = s
    return sim


def _mentions(name: str, other_origin: str) -> bool:
    key = re.sub(r"\s+", "", name or "")
    body = re.sub(r"\s+", "", other_origin or "")
    if len(key) < 2 or not body:
        return False
    # 조사로 끝이 바뀌니 앞뒤 부분일치까지 허용(이름의 앞 80% 또는 뒤 80%가 등장)
    k = max(2, int(len(key) * 0.8))
    return key in body or key[:k] in body or key[-k:] in body


def group(records: list[dict]) -> list[list[int]]:
    """records: [{name, origin, source}] → 같은 밈끼리 묶인 인덱스 그룹들.

    두 가지 안전장치(2026-09-22 전체 재수집에서 'OO 정보'가 '장원영 OO'와 한 덩어리로 묶인 사고 후 추가):
      · 이름 유사도를 잴 때 빈칸 표기(OO/00 등)는 지운다 — 'OO'가 겹친다고 이름이 닮은 게 아니다
      · 한 덩어리 안에 같은 사이트 레코드가 둘 이상 들어가지 않게 묶는다 — 한 사이트가 같은 밈을
        두 번 다루지는 않으므로, 전파(A↔B, B↔C)로 같은 사이트 둘이 이어지면 그건 잘못 이어진 것이다.
        그래서 유사도가 높은 쌍부터 묶고, 이미 그 사이트가 들어 있는 덩어리와는 합치지 않는다.
    """
    n = len(records)
    if n == 0:
        return []
    o = tfidf_cosine([r.get("origin") or "" for r in records])
    nm = tfidf_cosine([PLACEHOLDER.sub(" ", r.get("name") or "") for r in records])
    parent = list(range(n))
    sites = {i: {records[i].get("source")} for i in range(n)}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    pairs = []
    for i, j in combinations(range(n), 2):
        if records[i].get("source") == records[j].get("source"):
            continue
        so, sn = o[i][j], nm[i][j]
        mention = (_mentions(records[i]["name"], records[j].get("origin"))
                   and _mentions(records[j]["name"], records[i].get("origin")))
        if (sn >= NAME_T and so >= ORIGIN_LOW) or so >= ORIGIN_ONLY or (mention and so >= MENTION_T):
            pairs.append((so + sn, i, j))
    for _, i, j in sorted(pairs, reverse=True):
        a, b = find(i), find(j)
        if a == b or sites[a] & sites[b]:
            continue
        parent[a] = b
        sites[b] |= sites.pop(a)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


# 이름의 빈칸 표기 — 사이트마다 달라서 전부 같은 것으로 본다. '100드립'의 00처럼 숫자 사이는 빈칸이 아니다.
PLACEHOLDER = re.compile(r"(?<![0-9A-Za-z])(OO|oo|Oo|00|○○|ㅇㅇ|XX|xx|××)(?![0-9A-Za-z])")


def has_placeholder(name: str) -> bool:
    return bool(PLACEHOLDER.search(name or ""))


def pick_name(names: list[str]) -> str:
    """같은 밈의 이름 후보 중 대표 이름. 팀 결정(2026-09-22): 빈칸 표기(OO/00 등)가 없는 이름을 우선한다.
    네이버 검색어로 바로 쓸 수 있어서 유행 날짜 측정이 된다. 후보 순서(유래 짧은 대표가 앞)를 유지한다."""
    for n in names:
        if n and not has_placeholder(n):
            return n
    return names[0] if names else ""
