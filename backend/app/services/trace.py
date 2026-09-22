"""단계별 기록(trace) — 네컷 하나가 만들어지는 8단계의 **들어간 것·나온 것·시간·설정**을 통째로 남긴다.

왜: 프롬프트를 아무리 고쳐도 결과가 안 좋을 때, "어느 단계에서 틀어졌나"를 보려면 한 줄 로그가 아니라
단계마다 GPT 지시문 전체·GPT 원문 답변·시드·크롭 창까지 그대로 있어야 한다(2026-09-22 사용자 결정 — 역추적).

파일: backend/traces/<run_id>.jsonl — 한 줄이 한 단계. 광고 하나(제안 → 그림)에 파일 하나.
쓰는 법:
    tr = Tracer.start(kind="comic")           # 새 기록
    tr = Tracer.resume(run_id)                # 그림 단계에서 이어 쓰기(다른 요청·스레드)
    with use(tr): ...                         # 이 안에서 current() 가 tr — GPT·사전·그림 코드가 알아서 기록
    tr.step("대사 쓰기", who="gpt-4o", input={...}, output_raw="...", sec=1.2)
기록이 없어도 앱은 그대로 돈다 — current() 가 None 이면 전부 무시.
"""
from __future__ import annotations

import contextlib
import json
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from app.core.config import BACKEND_ROOT

TRACE_DIR = BACKEND_ROOT / "traces"
_local = threading.local()


class Tracer:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.path = TRACE_DIR / f"{run_id}.jsonl"
        self._n = 0
        if self.path.exists():
            self._n = sum(1 for _ in self.path.open(encoding="utf-8"))

    @classmethod
    def start(cls, kind: str = "comic", **meta: Any) -> "Tracer":
        TRACE_DIR.mkdir(parents=True, exist_ok=True)
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:4]
        tr = cls(run_id)
        tr.step("시작", who="code", kind=kind, **meta)
        return tr

    @classmethod
    def resume(cls, run_id: str | None) -> "Tracer | None":
        if not run_id or not (TRACE_DIR / f"{run_id}.jsonl").exists():
            return None
        return cls(run_id)

    def step(self, name: str, who: str = "code", **fields: Any) -> None:
        """한 단계를 한 줄로. fields 는 JSON 으로 적을 수 있는 것이면 무엇이든(지시문 전체·원문 답변 포함)."""
        self._n += 1
        row = {"i": self._n, "t": datetime.now().isoformat(timespec="seconds"), "name": name, "who": who}
        row.update(fields)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    def rows(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.open(encoding="utf-8") if l.strip()]


def current() -> Tracer | None:
    return getattr(_local, "tracer", None)


@contextlib.contextmanager
def use(tracer: Tracer | None) -> Iterator[Tracer | None]:
    prev = getattr(_local, "tracer", None)
    _local.tracer = tracer
    try:
        yield tracer
    finally:
        _local.tracer = prev


def step(name: str, who: str = "code", **fields: Any) -> None:
    """current() 가 있으면 기록, 없으면 무시. 라이브러리 코드(GPT·사전·그림)에서 부른다."""
    tr = current()
    if tr is not None:
        tr.step(name, who=who, **fields)


class timer:
    """with timer() as t: ...; t.sec"""
    def __enter__(self):
        self._t = time.time(); self.sec = 0.0; return self

    def __exit__(self, *a):
        self.sec = round(time.time() - self._t, 2)


def list_runs(limit: int = 30) -> list[dict]:
    if not TRACE_DIR.exists():
        return []
    out = []
    for p in sorted(TRACE_DIR.glob("*.jsonl"), reverse=True)[:limit]:
        n = sum(1 for _ in p.open(encoding="utf-8"))
        out.append({"run_id": p.stem, "steps": n, "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")})
    return out
