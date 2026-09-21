"""이미지 생성 — ComfyUI의 '연습용' 워크플로우를 그대로 호출한다.

워크플로우는 app/services/workflows/character_practice.json 이고, ComfyUI에 저장된
`연습용.json`(UI 포맷)을 API 포맷으로 변환한 것이다. 노드 구성·모델·샘플러·스텝을
바꾸지 않았으므로 ComfyUI 화면에서 돌린 결과와 같은 그림이 나온다.

호출부는 이 모듈을 **동기로 쓰지 않는다.** 1024px 30스텝 기준 실측이 1장 56초,
3장 86초인데 nginx proxy_read_timeout이 60초라 요청 스레드에서 기다리면 502가 난다.
app/services/jobs.py의 백그라운드 워커가 이 함수를 대신 호출한다.
"""

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

# 그림을 내려주는 경로. nginx가 /api/ 만 백엔드로 넘기므로 반드시 /api/ 로 시작해야 한다.
MEDIA_URL_PREFIX = "/api/media"

# PNG 매직 넘버. ComfyUI가 그림 대신 에러 페이지를 돌려주는 일이 있는데, 그걸 그대로
# 저장하면 화면엔 깨진 이미지 아이콘만 뜨고 로그엔 아무것도 안 남는다.
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# '연습용' 워크플로우의 네거티브 프롬프트를 그대로 쓴다. 사람·실사·글자를 배제하는 쪽으로
# 이미 조정돼 있어서, 마스코트를 뽑을 때 이걸 바꾸면 결과가 나빠진다.
# 네거티브는 **실존하는 Danbooru 태그로만** 적는다. 옛 목록은 사람·성인물을 막으려고
# human · human hands · nsfw · text 를 넣어 뒀는데, parquet로 대조해 보니 넷 다 죽은 말이었다
# (human 0장·폐기 / human hands 아예 없음 / nsfw 0장·폐기 / text 0장·폐기). 즉 지난 몇 주 동안
# 사람과 노출을 막는 장치가 **하나도 작동하지 않았다**. 실제로 "통통한 토끼"만 줬을 때
# 토끼귀 달린 사람이 수영복 차림으로 나왔다(2026-09-18 실측).
#
# 아래 태그는 전부 실존·2,000장 이상·일반 분류를 확인한 것이다. 바꾼 뒤 같은 시드로 재생성해
# 사람 형태가 동물로 돌아오는 것을 확인했다.
#
# 한계 두 가지 — ① 네컷 워크플로우(capanima_turbo, cfg 1.0)에서는 네거티브가 사실상 무효다.
# 이 목록은 캐릭터 후보 단계(cfg 5)에서만 듣는다. ② 특정 태그가 끌고 오는 의상 연상은
# 네거티브로 못 지운다 — bowtie를 넣으면 레오타드·손목 커프스가 같이 따라온다(아래 참고).
NEGATIVE_PROMPT = (
    "worst quality, low quality, score_1, score_2, score_3, artist name, blurry, "
    "jpeg artifacts, chromatic aberration, realistic, multiple_views, watermark, "
    # 사람 형태 — 마스코트는 동물이어야 한다
    "1girl, 1boy, fake_animal_ears, long_hair, breasts, cleavage, navel, "
    "bare_shoulders, collarbone, thighs, "
    # 노출·성인 의상
    "leotard, playboy_bunny, detached_collar, wrist_cuffs, swimsuit, one-piece_swimsuit, "
    "bikini, underwear, panties, lingerie, revealing_clothes, nude, nipples, "
    "thighhighs, pantyhose"
)

# 캐릭터를 '동물'로 못 박는 접두어. 토끼는 Danbooru에서 동물 토끼와 '토끼귀 소녀'가
# 섞여 있는 태그라, 털색(*_fur)이나 이 태그들이 없으면 사람 쪽으로 흐른다.
# 팀 공용 STYLE_TAGS에는 아직 없어 여기 상수로만 둔다 — 붙일지는 팀과 협의 후.
ANIMAL_ANCHOR_TAGS = "no_humans, animal_focus, furry"

# ComfyUI에서 Export(API format)한 그래프를 그대로 이 폴더에 넣어두면 코드 수정 없이 워크플로우를
# 교체할 수 있다 — 샘플러 노드의 positive/negative가 가리키는 CLIPTextEncode 노드를 찾아 자동으로
# 프롬프트를 채워 넣으므로, ComfyUI에서 내보낸 원본을 그대로 갖다 놓으면 된다.
WORKFLOWS_DIR = Path(__file__).parent / "workflows"

_POLL_INTERVAL_SECONDS = 2

# 실측값 (L4 24GB, 모델 로드된 상태). 화면에서 "약 N초 남았어요"를 보여주는 근거.
SECONDS_PER_IMAGE = 30
SECONDS_BASE = 26


def eta_seconds(count: int = 1) -> int:
    """count장을 뽑는 데 걸리는 예상 시간(초). 대기 중 화면에 남은 시간을 보여주는 데 쓴다."""
    return SECONDS_BASE + SECONDS_PER_IMAGE * max(count, 1)


def _load_workflow(name: str | None = None) -> dict:
    path = Path(name or settings.comfy_workflow_file)
    if not path.is_absolute():
        path = WORKFLOWS_DIR / path
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _build_prompt_graph(text: str, seed: int, batch_size: int = 1,
                        workflow_file: str | None = None, reference_name: str | None = None,
                        size: tuple[int, int] | None = None, ip_strength: float | None = None,
                        ip_start_at: float | None = None) -> dict:
    graph = _load_workflow(workflow_file)

    # 캔버스 크기 덮어쓰기 — 캐릭터를 한쪽에 두려고 넓게 뽑아 자를 때 쓴다.
    if size:
        for node in graph.values():
            if node.get("class_type") == "EmptyLatentImage":
                node["inputs"]["width"], node["inputs"]["height"] = size
    # IP-Adapter 강도·시작점 덮어쓰기 — 참조 그림이 구도까지 끌고 오는 걸 누그러뜨리는 실험용.
    for node in graph.values():
        if node.get("class_type") == "AnimaIPAdapterApply":
            if ip_strength is not None:
                node["inputs"]["strength"] = ip_strength
            if ip_start_at is not None:
                node["inputs"]["start_at"] = ip_start_at

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

    # 참조 이미지 노드(LoadImage)가 있는 그래프면 ComfyUI에 올려둔 파일명을 꽂는다.
    if reference_name:
        for node in graph.values():
            if node.get("class_type") == "LoadImage":
                node["inputs"]["image"] = reference_name

    # 후보 3장을 한 번에 뽑을 때는 batch_size를 올린다. 3번 따로 돌리면 168초인데
    # 배치로 돌리면 86초다 (모델 로드·VAE 디코드가 한 번이라서).
    if batch_size > 1:
        for node in graph.values():
            inputs = node.get("inputs", {})
            if isinstance(inputs.get("batch_size"), int):
                inputs["batch_size"] = batch_size

    return graph


def _comfy_request(method: str, path: str, **kwargs) -> requests.Response:
    auth = HTTPBasicAuth(settings.comfy_user, settings.comfy_password) if settings.comfy_user else None
    return requests.request(method, f"{settings.comfy_base_url}{path}", auth=auth, timeout=30, **kwargs)


def _save_png(content: bytes) -> str | None:
    """PNG 바이트를 media 디렉터리에 저장하고 내려받을 URL을 돌려준다.

    PNG가 아니면 저장하지 않고 None — 호출부가 그 칸을 'failed'로 표시한다.
    깨진 파일을 URL로 돌려주면 사장님 화면엔 이유 없는 빈 칸만 남는다.
    """
    if not content.startswith(_PNG_MAGIC):
        logger.warning("ComfyUI가 PNG가 아닌 응답을 돌려줬습니다 (%d bytes)", len(content))
        return None
    filename = f"{uuid.uuid4().hex}.png"
    (settings.media_path / filename).write_bytes(content)
    return f"{MEDIA_URL_PREFIX}/{filename}"


def _upload_reference(path: Path) -> str | None:
    """참조 PNG를 ComfyUI input/에 올리고 LoadImage에 넣을 파일명을 돌려준다. 실패하면 None."""
    try:
        with open(path, "rb") as f:
            resp = _comfy_request("POST", "/upload/image",
                                  files={"image": (path.name, f, "image/png")},
                                  data={"overwrite": "true"})
        resp.raise_for_status()
        return resp.json().get("name") or path.name
    except (OSError, requests.RequestException, ValueError):
        logger.exception("참조 이미지 업로드 실패: %s", path)
        return None


def _crop_png(content: bytes, crop: tuple[int, int, int, int]) -> bytes:
    """(x0, y0, w, h) 로 자른 PNG 바이트. 넓게 뽑은 그림에서 캐릭터가 한쪽에 오도록 창을 옮겨 자른다."""
    from io import BytesIO
    from PIL import Image
    x0, y0, w, h = crop
    im = Image.open(BytesIO(content))
    x0 = max(0, min(x0, im.width - w))
    y0 = max(0, min(y0, im.height - h))
    buf = BytesIO()
    im.crop((x0, y0, x0 + w, y0 + h)).save(buf, format="PNG")
    return buf.getvalue()


# 캐릭터 위치. 그림 모델엔 "왼쪽에 둬라"는 태그가 없어서 정사각(1216²)으로 뽑고 832×1216 창을 옮겨 자른다.
# 캐릭터는 가운데(x=608)에 오므로, 창을 오른쪽으로 밀면 캐릭터가 왼쪽에 남고 오른쪽이 빈다(말풍선 자리).
POSITION_CANVAS = (1216, 1216)
POSITION_CROP = {"왼쪽": (384, 0, 832, 1216), "가운데": (192, 0, 832, 1216), "오른쪽": (0, 0, 832, 1216)}


def generate_images(prompt: str, count: int = 1, seed: int | None = None,
                    workflow_file: str | None = None, reference_path: Path | None = None,
                    position: str | None = None, ip_strength: float | None = None,
                    ip_start_at: float | None = None) -> list[str | None]:
    """ComfyUI로 이미지 count장을 생성해 **URL 목록**을 반환한다 (`/api/media/<uuid>.png`).

    PNG는 디스크(settings.media_path)에 저장하고 응답엔 경로만 담는다 — 예전처럼
    base64를 DB에 넣으면 /api/character 한 번이 1.9MB가 되어 3초마다 도는 폴링에
    그대로 실려 나간다.
    설정이 비어있거나 생성에 실패하면 빈 목록을 반환 — 호출부가 실패 상태로 표시한다."""
    if not settings.comfy_base_url:
        logger.warning("COMFY_BASE_URL이 비어 있어 이미지를 생성할 수 없습니다")
        return []

    seed = seed if seed is not None else random.randint(0, 2**32 - 1)
    client_id = str(uuid.uuid4())

    reference_name = None
    if reference_path is not None:
        reference_name = _upload_reference(reference_path)
        if not reference_name:
            return []

    size = POSITION_CANVAS if position in POSITION_CROP else None
    crop = POSITION_CROP.get(position or "")
    try:
        submit = _comfy_request("POST", "/prompt", json={
            "client_id": client_id,
            "prompt": _build_prompt_graph(prompt, seed, count, workflow_file, reference_name,
                                          size=size, ip_strength=ip_strength, ip_start_at=ip_start_at),
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
            return []

        if history.get("status", {}).get("status_str") != "success":
            logger.warning("ComfyUI generation failed for prompt_id=%s: %s", prompt_id, history.get("status"))
            return []

        images = []
        for output in history.get("outputs", {}).values():
            images.extend(output.get("images", []))
        if not images:
            return []

        out = []
        for image in images[:count]:
            view = _comfy_request("GET", "/view", params={
                "filename": image["filename"],
                "subfolder": image.get("subfolder", ""),
                "type": image.get("type", "output"),
            })
            view.raise_for_status()
            # 저장에 실패해도 자리를 비워 둔 채로 넣는다. 건너뛰면 뒤 그림이 앞 칸으로
            # 당겨져 '후보2' 자리에 후보3 그림이 걸린다.
            out.append(_save_png(_crop_png(view.content, crop) if crop else view.content))
        return out
    except requests.RequestException:
        logger.exception("ComfyUI request failed")
        return []


def generate_image(prompt: str, seed: int | None = None) -> str | None:
    """이미지 한 장. 실패하면 None."""
    images = generate_images(prompt, 1, seed)
    return images[0] if images else None
