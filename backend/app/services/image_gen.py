"""이미지 생성. ComfyUI(Anima 모델)에 연결되어 있으면 실제 이미지를 생성해서
data URI로 돌려주고, 설정이 없거나 서버 연결에 실패하면 hue 그라디언트로 폴백한다
(frontend/src/theme.js의 bgGradient와 동일한 규칙)."""

import base64
import json
import logging
import random
import time
import uuid
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

from app.core.config import settings

logger = logging.getLogger(__name__)

NEGATIVE_PROMPT = "worst quality, low quality, blurry, jpeg artifacts, text, watermark, extra limbs, deformed"

# ComfyUI에서 Export(API format)한 그래프를 그대로 이 폴더에 넣어두면 코드 수정 없이 워크플로우를
# 교체할 수 있다 — 샘플러 노드의 positive/negative가 가리키는 CLIPTextEncode 노드를 찾아 자동으로
# 프롬프트를 채워 넣으므로, ComfyUI에서 내보낸 원본을 그대로 갖다 놓으면 된다.
WORKFLOWS_DIR = Path(__file__).parent / "workflows"

_POLL_INTERVAL_SECONDS = 2


def random_hue() -> int:
    return random.randint(0, 359)


def _load_workflow() -> dict:
    path = Path(settings.comfy_workflow_file)
    if not path.is_absolute():
        path = WORKFLOWS_DIR / path
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _build_prompt_graph(text: str, seed: int) -> dict:
    graph = _load_workflow()

    # 샘플러 노드의 positive/negative가 가리키는 노드를 따라가 그 노드의 text를 치환한다.
    for node in graph.values():
        inputs = node.get("inputs", {})
        for key, value in (("positive", text), ("negative", NEGATIVE_PROMPT)):
            ref = inputs.get(key)
            if isinstance(ref, list) and len(ref) == 2:
                target = graph.get(str(ref[0]))
                if target and isinstance(target.get("inputs", {}).get("text"), str):
                    target["inputs"]["text"] = value

    # seed / noise_seed 자동 채움
    for node in graph.values():
        inputs = node.get("inputs", {})
        if isinstance(inputs.get("seed"), int):
            inputs["seed"] = seed
        if isinstance(inputs.get("noise_seed"), int):
            inputs["noise_seed"] = seed

    return graph


def _comfy_request(method: str, path: str, **kwargs) -> requests.Response:
    auth = HTTPBasicAuth(settings.comfy_user, settings.comfy_password) if settings.comfy_user else None
    return requests.request(method, f"{settings.comfy_base_url}{path}", auth=auth, timeout=30, **kwargs)


def generate_image(prompt: str, seed: int | None = None) -> str | None:
    """ComfyUI로 이미지 한 장을 생성해 data URI(base64 PNG)로 반환한다.
    설정이 비어있거나 생성에 실패하면 None을 반환 — 호출부는 hue 폴백을 유지한다."""
    if not settings.comfy_base_url:
        return None

    seed = seed if seed is not None else random.randint(0, 2**32 - 1)
    client_id = str(uuid.uuid4())

    try:
        submit = _comfy_request("POST", "/prompt", json={
            "client_id": client_id,
            "prompt": _build_prompt_graph(prompt, seed),
        })
        submit.raise_for_status()
        prompt_id = submit.json()["prompt_id"]

        deadline = time.monotonic() + settings.comfy_timeout_seconds
        history = None
        while time.monotonic() < deadline:
            time.sleep(_POLL_INTERVAL_SECONDS)
            resp = _comfy_request("GET", f"/history/{prompt_id}")
            resp.raise_for_status()
            body = resp.json()
            if prompt_id in body:
                history = body[prompt_id]
                break
        if history is None:
            logger.warning("ComfyUI generation timed out for prompt_id=%s", prompt_id)
            return None

        if history.get("status", {}).get("status_str") != "success":
            logger.warning("ComfyUI generation failed for prompt_id=%s: %s", prompt_id, history.get("status"))
            return None

        images = []
        for output in history.get("outputs", {}).values():
            images.extend(output.get("images", []))
        if not images:
            return None

        image = images[0]
        view = _comfy_request("GET", "/view", params={
            "filename": image["filename"], "subfolder": image.get("subfolder", ""), "type": image.get("type", "output"),
        })
        view.raise_for_status()
        encoded = base64.b64encode(view.content).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except requests.RequestException:
        logger.exception("ComfyUI request failed")
        return None
