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
    table = pq.read_table(path, columns=["name", "post_count"])
    names = table.column("name").to_pylist()
    counts = table.column("post_count").to_pylist()
    return {n: c for n, c in zip(names, counts) if c is not None and c >= MIN_POST_COUNT}


def verify_tags(candidates: list[str]) -> list[str]:
    """존재하고 post_count >= 2,000인 태그만, 중복 제거해서 원래 순서대로 돌려준다."""
    valid = _valid_tags()
    seen: set[str] = set()
    result: list[str] = []
    for raw in candidates:
        tag = raw.strip().strip(",")
        if tag and tag in valid and tag not in seen:
            result.append(tag)
            seen.add(tag)
    return result
