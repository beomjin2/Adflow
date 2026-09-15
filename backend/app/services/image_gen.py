"""이미지 생성. ComfyUI(Anima 모델)에 연결되어 있으면 실제 이미지를 생성해서
data URI로 돌려주고, 설정이 없거나 서버 연결에 실패하면 hue 그라디언트로 폴백한다
(frontend/src/theme.js의 bgGradient와 동일한 규칙)."""

import base64
import logging
import random
import time
import uuid

import requests
from requests.auth import HTTPBasicAuth

from app.core.config import settings

logger = logging.getLogger(__name__)

NEGATIVE_PROMPT = "worst quality, low quality, blurry, jpeg artifacts, text, watermark, extra limbs, deformed"

_POLL_INTERVAL_SECONDS = 2


def random_hue() -> int:
    return random.randint(0, 359)


def _build_prompt_graph(text: str, seed: int, width: int = 768, height: int = 768) -> dict:
    return {
        "1": {"class_type": "UNETLoader", "inputs": {
            "unet_name": settings.comfy_unet_name, "weight_dtype": "default",
        }},
        "2": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": settings.comfy_clip_name, "type": "stable_diffusion",
        }},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": settings.comfy_vae_name}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": text, "clip": ["2", 0]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIVE_PROMPT, "clip": ["2", 0]}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0],
            "seed": seed, "steps": 30, "cfg": 4, "sampler_name": "euler", "scheduler": "simple", "denoise": 1,
        }},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "character"}},
    }


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
