"""마지막 컷 간판 검사 — 그림 모델이 제 입간판을 그렸는지 태거(WD14 ViT v3, ONNX)로 본다.

왜: 프롬프트에서 sign 을 빼도 모델이 가끔 칠판·입간판을 그려서(09-22 실측 3/3 첫 시도) 우리가 얹는 입간판과
두 개가 된다. 위치를 알 수는 없으니, 검출되면 시드를 바꿔 다시 뽑는다(호출부, 최대 2번).
선택 기능: settings.wd14_dir 에 model.onnx + selected_tags.csv 가 있을 때만 켜진다. 없으면 None(검사 생략).
onnxruntime 은 numpy/pandas 보다 먼저 import 해야 한다(Windows 에서 segfault) — 그래서 여기서 지연 import.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import BACKEND_ROOT, settings

logger = logging.getLogger(__name__)

SIGN_TAGS = {"sign", "chalkboard", "menu_board", "signboard", "billboard"}
_session = None
_tags: list[str] = []


def available() -> bool:
    d = Path(settings.wd14_dir)
    if not d.is_absolute():
        d = BACKEND_ROOT / d
    return (d / "model.onnx").is_file() and (d / "selected_tags.csv").is_file()


def _load():
    global _session, _tags
    if _session is not None:
        return
    import onnxruntime as ort  # noqa: F401  (numpy 보다 먼저)
    import csv
    d = Path(settings.wd14_dir)
    if not d.is_absolute():
        d = BACKEND_ROOT / d
    _session = ort.InferenceSession(str(d / "model.onnx"), providers=["CPUExecutionProvider"])
    with open(d / "selected_tags.csv", encoding="utf-8") as f:
        _tags = [row["name"] for row in csv.DictReader(f)]


def sign_tags(image_path: Path, thr: float = 0.35) -> list[str] | None:
    """그림에서 읽힌 간판류 태그. 검사를 못 하면 None."""
    if not available():
        return None
    try:
        _load()
        import numpy as np
        from PIL import Image
        im = Image.open(image_path).convert("RGB")
        size = _session.get_inputs()[0].shape[1] or 448
        s = max(im.size)
        canvas = Image.new("RGB", (s, s), (255, 255, 255)); canvas.paste(im, ((s - im.width) // 2, (s - im.height) // 2))
        canvas = canvas.resize((size, size), Image.BICUBIC)
        x = np.asarray(canvas, dtype=np.float32)[:, :, ::-1][None]   # BGR
        probs = _session.run(None, {_session.get_inputs()[0].name: x})[0][0]
        got = {t for t, p in zip(_tags, probs) if p >= thr}
        return sorted(got & SIGN_TAGS)
    except Exception:
        logger.exception("간판 검사 실패 — 검사 없이 진행")
        return None
