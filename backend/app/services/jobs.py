"""이미지 생성 백그라운드 워커.

왜 필요한가 — 실측으로 1024px 30스텝 1장이 56초, 3장이 86초다. nginx의
proxy_read_timeout이 60초라서 요청 스레드에서 ComfyUI를 기다리면 **502 Bad Gateway**가 난다.
모바일에서는 그 전에 연결이 끊기고, 사장님이 화면을 닫으면 작업이 통째로 사라진다.

그래서 요청과 결과를 분리한다.
    POST /api/character/candidates  → 즉시 반환. 칸 3개가 status="generating"으로 생긴다
    GET  /api/character             → 화면이 3초마다 폴링. 다 되면 status="done" + image

GPU는 1장뿐이라 동시 실행을 1로 묶는다(Semaphore). 두 건이 동시에 돌면 RAM 16GB에서
OOM이 나고, OOM killer가 엉뚱한 프로세스를 죽여 증상이 매번 달라 보인다.
"""

import logging
import threading
import time

from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

# GPU 1장 = 동시 생성 1건. 뒤에 들어온 건은 큐에서 기다린다.
_gpu = threading.Semaphore(1)

# 지금 대기 중인 건수 — 화면에 "앞에 N명"을 보여주는 데 쓴다.
_waiting = 0
_waiting_lock = threading.Lock()


def queue_depth() -> int:
    """자기 차례를 기다리는 작업 수."""
    with _waiting_lock:
        return _waiting


def submit(fn, *args, **kwargs) -> None:
    """fn을 백그라운드에서 실행한다. GPU 슬롯이 빌 때까지 기다린 뒤 실행한다.

    fn은 DB 세션을 직접 열어야 한다 — 요청 스레드의 세션은 응답이 끝나면 닫히므로
    그걸 넘겨받아 쓰면 안 된다.
    """

    def runner():
        global _waiting
        with _waiting_lock:
            _waiting += 1
        try:
            _gpu.acquire()
        finally:
            with _waiting_lock:
                _waiting -= 1
        started = time.monotonic()
        try:
            fn(*args, **kwargs)
        except Exception:
            logger.exception("background image job failed")
        finally:
            _gpu.release()
            logger.info("image job finished in %.1fs", time.monotonic() - started)

    threading.Thread(target=runner, daemon=True).start()


def with_session(fn):
    """백그라운드 작업용 DB 세션을 열어 fn(db)를 실행하고 반드시 닫는다."""
    db = SessionLocal()
    try:
        return fn(db)
    finally:
        db.close()
