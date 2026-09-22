"""GPT가 생성한 Danbooru 태그 후보를, 실제 Danbooru 태그 전체 목록에 대고 검증한다.

CLAUDE.md 5-1: 실존하고 post count 2,000 이상인 태그만 쓴다. 태그 하나하나를 사람이
확인하는 대신, HuggingFace `deepghs/site_tags`(dataset, CC-BY-4.0) 중
danbooru.donmai.us/tags.parquet 미러(159만 행, name+post_count)를 통째로 대조한다.
Danbooru 자체 API는 대량 조회를 막아놔서 이 미러를 쓴다(research/34, 47).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import pyarrow.parquet as pq

from app.core.config import BACKEND_ROOT, settings

logger = logging.getLogger(__name__)

MIN_POST_COUNT = 2000

# Danbooru 태그 분류. 우리가 쓸 수 있는 건 **일반(0)** 과 **메타(5)** 뿐이다.
#   1 작가명 · 3 작품명 · 4 캐릭터명 → 특정 애니의 인물·작품·그린 사람을 가리킨다.
# 장수만 보고 걸렀더니 2,000장 이상 8,410개 중 2,070개(25%)가 이쪽이었다
# (캐릭터명 1,314 · 작품명 624 · 작가명 87 · 폐기 46 — 2026-09-17 실측).
# 그게 사장님 마스코트 프롬프트에 섞이면 그건 더 이상 사장님 캐릭터가 아니다.
ALLOWED_CATEGORIES = (0, 5)


@lru_cache(maxsize=1)
def _valid_tags() -> dict[str, int]:
    path = Path(settings.danbooru_tags_path)
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    # parquet는 159만 행짜리라 저장소에 없다(backend/.gitignore). 배포 서버에 아직
    # 내려받지 않았으면 여기서 죽는 대신 빈 사전을 돌려준다 — 그러면 verify_tags가
    # 전부 버리고 tags_for_look이 화이트리스트로 폴백한다. 검증을 건너뛰고 통과시키는
    # 반대 방향은 위험하다: GPT가 지어낸 태그가 그대로 프롬프트에 들어간다.
    if not path.exists():
        logger.warning(
            "Danbooru 태그 목록이 없습니다(%s) — 태그 검증을 건너뛰고 화이트리스트로 폴백합니다", path
        )
        return {}
    wanted = ["name", "post_count", "category", "is_deprecated"]
    have = set(pq.read_schema(path).names)
    table = pq.read_table(path, columns=[c for c in wanted if c in have])

    def column(name, default):
        return table.column(name).to_pylist() if name in have else [default] * table.num_rows

    names = table.column("name").to_pylist()
    counts = table.column("post_count").to_pylist()
    categories = column("category", 0)
    deprecated = column("is_deprecated", False)

    return {
        name: count
        for name, count, category, is_dep in zip(names, counts, categories, deprecated)
        if count is not None and count >= MIN_POST_COUNT
        and category in ALLOWED_CATEGORIES
        and not is_dep
    }


def verify_tags(candidates: list[str]) -> list[str]:
    """쓸 수 있는 태그만 중복 없이 원래 순서대로. 조건은 세 가지다 —
    실존하고 post_count >= 2,000, 분류가 일반·메타, 폐기되지 않았을 것.

    띄어쓰기는 밑줄로 바꿔 조회한다. Danbooru 표기는 밑줄인데 GPT가 'red scarf'처럼
    띄어 쓰는 일이 잦아서, 실존하는 태그가 표기 때문에 버려지던 걸 막는다.
    돌려줄 때는 Danbooru 표기(밑줄)로 통일한다.
    """
    valid = _valid_tags()
    seen: set[str] = set()
    result: list[str] = []
    rejected: list[str] = []
    for raw in candidates:
        tag = raw.strip().strip(",").replace(" ", "_")
        if tag and tag in valid and tag not in seen:
            result.append(tag)
            seen.add(tag)
        elif tag and tag not in seen:
            rejected.append(tag)
    # 뜯어보기: 기록 중이면 탈락 이유(없음/장수 부족/분류/폐기)까지 남긴다 — 기록이 없을 땐 비용 0
    from app.services import trace
    if trace.current() is not None:
        trace.step("사전 확인", who="code", candidates=list(candidates), verified=result,
                   rejected=explain_tags(rejected) if rejected else {})
    return result


_CATEGORY_KO = {0: "일반", 1: "작가 이름", 3: "작품 이름", 4: "캐릭터 이름", 5: "메타"}


def explain_tags(tags: list[str]) -> dict[str, str]:
    """탈락한 후보가 **왜** 떨어졌나. 원본 parquet 를 그 태그들만 걸러 읽는다(몇 개라 빠르다). 뜯어보기용."""
    if not tags:
        return {}
    path = Path(settings.danbooru_tags_path)
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    if not path.exists():
        return {t: "사전 파일 없음" for t in tags}
    wanted = ["name", "post_count", "category", "is_deprecated"]
    have = set(pq.read_schema(path).names)
    table = pq.read_table(path, columns=[c for c in wanted if c in have], filters=[("name", "in", list(tags))])
    found = {row["name"]: row for row in table.to_pylist()}
    out = {}
    for t in tags:
        r = found.get(t)
        if r is None:
            out[t] = "사전에 없는 말"
        elif r.get("is_deprecated"):
            out[t] = f"폐기된 태그 ({r.get('post_count'):,}장)"
        elif r.get("category", 0) not in ALLOWED_CATEGORIES:
            out[t] = f"{_CATEGORY_KO.get(r.get('category'), r.get('category'))}이라 못 씀 ({r.get('post_count'):,}장)"
        elif (r.get("post_count") or 0) < MIN_POST_COUNT:
            out[t] = f"{r.get('post_count'):,}장뿐 (2,000장 미만)"
        else:
            out[t] = "중복"
    return out
