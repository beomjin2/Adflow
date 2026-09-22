"""마지막 컷 간판 검사 — 그림 모델이 제 입간판을 그렸는지 태거(WD14 ViT v3, ONNX)로 본다.

왜: 프롬프트에서 sign 을 빼도 모델이 가끔 칠판·입간판을 그려서(09-22 실측 3/3 첫 시도) 우리가 얹는 입간판과
두 개가 된다. 위치를 알 수는 없으니, 검출되면 시드를 바꿔 다시 뽑는다(호출부, 최대 2번).
선택 기능: settings.wd14_dir 에 model.onnx + selected_tags.csv 가 있을 때만 켜진다. 없으면 None(검사 생략).

**별도 프로세스에서 돈다.** onnxruntime 은 numpy/pyarrow 보다 먼저 import 돼야 하는데(Windows 에서 segfault),
서버 프로세스엔 이미 둘이 올라와 있어 같은 프로세스에서 부르면 서버가 소리 없이 죽는다 — 09-22 진짜 e2e 에서
4컷 직후 백엔드가 통째로 내려갔다. 그래서 `python -m app.services.sign_check <png>` 로 자식 프로세스를 띄운다.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

from app.core.config import BACKEND_ROOT, settings

logger = logging.getLogger(__name__)

SIGN_TAGS = {"sign", "chalkboard", "menu_board", "signboard", "billboard"}


def _dir() -> Path:
    d = Path(settings.wd14_dir)
    return d if d.is_absolute() else BACKEND_ROOT / d


def available() -> bool:
    d = _dir()
    return (d / "model.onnx").is_file() and (d / "selected_tags.csv").is_file()


def sign_tags(image_path: Path, thr: float = 0.35) -> list[str] | None:
    """그림에서 읽힌 간판류 태그. 검사를 못 하면 None."""
    if not available():
        return None
    try:
        r = subprocess.run([sys.executable, "-m", "app.services.sign_check", str(image_path), str(thr)],
                           cwd=str(BACKEND_ROOT), capture_output=True, text=True, timeout=120, encoding="utf-8")
        if r.returncode != 0:
            logger.warning("간판 검사 자식 프로세스 실패(%s): %s", r.returncode, r.stderr[-300:])
            return None
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        logger.exception("간판 검사 실패 — 검사 없이 진행")
        return None


def _run(image_path: str, thr: float) -> list[str]:
    import onnxruntime as ort   # numpy 보다 먼저 — 이 순서가 이 파일의 존재 이유다
    import csv
    import numpy as np
    from PIL import Image
    d = _dir()
    session = ort.InferenceSession(str(d / "model.onnx"), providers=["CPUExecutionProvider"])
    with open(d / "selected_tags.csv", encoding="utf-8") as f:
        tags = [row["name"] for row in csv.DictReader(f)]
    im = Image.open(image_path).convert("RGB")
    size = session.get_inputs()[0].shape[1] or 448
    s = max(im.size)
    canvas = Image.new("RGB", (s, s), (255, 255, 255)); canvas.paste(im, ((s - im.width) // 2, (s - im.height) // 2))
    canvas = canvas.resize((size, size), Image.BICUBIC)
    x = np.asarray(canvas, dtype=np.float32)[:, :, ::-1][None]   # BGR
    probs = session.run(None, {session.get_inputs()[0].name: x})[0][0]
    got = {t for t, p in zip(tags, probs) if p >= thr}
    return sorted(got & SIGN_TAGS)


if __name__ == "__main__":
    print(json.dumps(_run(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 0.35)))
