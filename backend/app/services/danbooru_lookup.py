"""GPT가 생성한 Danbooru 태그 후보를, 실제 Danbooru 태그 전체 목록에 대고 검증한다.

CLAUDE.md 5-1: 실존하고 post count 2,000 이상인 태그만 쓴다. 태그 하나하나를 사람이
확인하는 대신, HuggingFace `deepghs/site_tags`(dataset, CC-BY-4.0) 중
danbooru.donmai.us/tags.parquet 미러(159만 행, name+post_count)를 통째로 대조한다.
Danbooru 자체 API는 대량 조회를 막아놔서 이 미러를 쓴다(research/34, 47).
"""

from __future__ import annotations

import logging
import threading
import time
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

# 사전은 159만 행·79MB라 처음 읽는 데 약 17초가 걸린다. 그래서 두 가지를 같이 둔다.
#
# 1) **잠금** — 예전에는 functools.lru_cache를 썼는데, 그건 "이미 만든 값"만 재사용할 뿐
#    **동시에 들어온 첫 호출을 막지 않는다**(3개 스레드가 동시에 처음 부르면 3번 다 실행된다.
#    직접 재현해 확인했다). 그래서 사장님이 생성 버튼을 세 번 연타하면 17초짜리 읽기가
#    세 번 겹쳐 **응답이 66.6초**가 됐다 — 배포 환경의 응답 한도 60초를 넘겨 502가 난다.
#    아래처럼 잠금 + 이중 확인을 두면 여럿이 동시에 와도 **한 번만** 읽는다.
#
# 2) **미리 읽기** — warm_cache()를 앱이 뜰 때 백그라운드로 부른다(main.py). 그러면 첫
#    사장님이 17초를 기다리는 일 자체가 없어진다. 서버 기동은 그대로 빠르다.
_cache: dict[str, int] | None = None
_cache_lock = threading.Lock()


def _valid_tags() -> dict[str, int]:
    """쓸 수 있는 태그 사전. 처음 한 번만 읽고 그 뒤로는 바로 돌려준다."""
    global _cache
    if _cache is not None:          # 흔한 경우 — 잠금 없이 바로
        return _cache
    with _cache_lock:
        if _cache is None:          # 잠금을 기다리는 사이 남이 채웠을 수 있다
            started = time.monotonic()
            _cache = _load_tags()
            logger.info("Danbooru 태그 사전 %d개를 %.1f초에 읽었습니다",
                        len(_cache), time.monotonic() - started)
        return _cache


def warm_cache() -> None:
    """사전을 미리 읽어둔다. 앱 시작 때 백그라운드에서 부른다 — 실패해도 서비스는 떠야 하므로
    예외를 밖으로 내보내지 않는다(사전이 없으면 화이트리스트로 폴백한다)."""
    try:
        _valid_tags()
    except Exception:
        logger.exception("태그 사전 미리 읽기 실패 — 첫 요청 때 다시 시도합니다")


def _load_tags() -> dict[str, int]:
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
    for raw in candidates:
        tag = raw.strip().strip(",").replace(" ", "_")
        if tag and tag in valid and tag not in seen:
            result.append(tag)
            seen.add(tag)
    return result
