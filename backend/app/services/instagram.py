"""인스타그램 게시 — 완성본 한 장 + 캡션을 사장님 계정에 올린다.

Instagram API with Instagram Login(비즈니스·크리에이터 계정 전용) 경로다. 2026-09-13에
계정 전환부터 실제 게시까지 손으로 한 번 해보고 되는 걸 확인한 흐름을 그대로 코드로 옮겼다.

    1. POST /{ig_user_id}/media          image_url·caption  → creation_id
    2. GET  /{creation_id}?status_code   FINISHED 될 때까지  (인스타가 이미지를 받아 가는 시간)
    3. POST /{ig_user_id}/media_publish  creation_id        → media_id
    4. GET  /{media_id}?fields=permalink 사장님에게 보여줄 링크

**왜 이미지를 다시 굽나** — 인스타 피드는 세로 4:5(0.8)까지만 받는다. 우리 완성본은 컷
하나가 832×1216(0.68)이라 그대로 올리면 거절된다. 그래서 좌우에 흰 여백을 채워 4:5로
맞추고 JPEG 로 저장한 새 파일을 올린다. 원본은 그대로 둔다 — 내려받기는 원본을 쓴다.

**왜 URL 로 올리나** — 인스타는 파일 업로드를 받지 않고 우리 서버의 이미지를 자기가
가져간다. 그래서 `public_base_url`(인스타가 열 수 있는 주소)이 반드시 있어야 한다.
localhost 는 인스타가 못 연다.

실패하면 InstagramError 를 던진다. 메시지에 인스타가 준 말을 그대로 담는다 — 원인 대부분이
토큰 만료나 이미지 주소 문제라, 그 메시지가 곧 해결 방법이다.
"""
from __future__ import annotations

import datetime as dt
import logging
import time
import uuid
from pathlib import Path

import requests
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)

TIMEOUT = 30            # 한 번의 API 호출
REFRESH_BEFORE_DAYS = 20   # 만료가 이만큼 남았으면 미리 갱신한다(장기 토큰은 60일)
POLL_TRIES, POLL_WAIT = 12, 3   # 컨테이너가 FINISHED 될 때까지 최대 36초
TARGET_RATIO = 4 / 5    # 인스타 피드 세로 한계


class InstagramError(RuntimeError):
    """게시 실패. 사장님 화면에 그대로 보여줄 한국어 메시지를 담는다."""


def creds() -> tuple[str, str]:
    """(사용자 ID, 액세스 토큰). 사장님이 온보딩 화면에서 연결한 값이 먼저고, 없으면 .env.

    DB를 먼저 보는 이유 — 서비스를 쓰는 사장님마다 계정이 다르다. .env 는 개발·시연용 폴백이다.
    """
    try:
        from app.core.database import SessionLocal
        from app import models
        db = SessionLocal()
        try:
            row = db.get(models.InstagramAccount, 1)
            if row and row.user_id and row.access_token:
                return row.user_id, row.access_token
        finally:
            db.close()
    except Exception:            # DB가 아직 없거나 조회 실패 — 설정으로 넘어간다
        logger.debug("인스타 계정 조회 실패 — .env 설정을 씁니다", exc_info=True)
    return settings.instagram_user_id, settings.instagram_access_token


def available() -> bool:
    """연결됐는가. 하나라도 비면 화면에서 게시 버튼을 숨긴다."""
    uid, token = creds()
    return bool(uid and token and settings.public_base_url)


def missing_reason() -> str:
    uid, token = creds()
    if not uid or not token:
        return "인스타 계정이 연결되지 않았어요 — 설정에서 계정을 먼저 연결해 주세요"
    if not settings.public_base_url:
        return "인스타가 이미지를 가져갈 주소가 없어요 (PUBLIC_BASE_URL)"
    return ""


def _api(method: str, path: str, **params) -> dict:
    url = f"{settings.instagram_api_base.rstrip('/')}/{path.lstrip('/')}"
    params.setdefault("access_token", creds()[1])
    try:
        r = requests.request(method, url, params=params, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise InstagramError(f"인스타그램에 연결하지 못했어요 — {e}") from e
    try:
        data = r.json()
    except ValueError:
        raise InstagramError(f"인스타그램 응답을 읽지 못했어요 (HTTP {r.status_code})")
    if r.status_code >= 400 or "error" in data:
        msg = (data.get("error") or {}).get("message") or f"HTTP {r.status_code}"
        raise InstagramError(f"인스타그램이 거절했어요 — {msg}")
    return data


def verify(token: str) -> tuple[str, str, str]:
    """온보딩에서 받은 토큰을 확인한다 → (계정 이름, 실제로 저장할 토큰, 만료 예정일).

    앱 대시보드에서 받은 토큰은 이미 60일짜리 장기 토큰이라 ig_exchange_token 으로 바꿀 수
    없다(그래서 09-13·09-25 두 번 452 가 났다). 대신 refresh 를 한 번 시도해 본다 —
    되면 만료일을 정확히 알 수 있고 그 시점부터 다시 60일이 된다. 만들어진 지 24시간이
    안 된 토큰은 refresh 가 안 되므로, 그때는 문서값(60일)으로 만료일을 잡아둔다.
    """
    username = account_name(token)          # 실패하면 InstagramError 가 그대로 올라간다
    try:
        data = _api("GET", "refresh_access_token", grant_type="ig_refresh_token", access_token=token)
        fresh = str(data.get("access_token") or "")
        if fresh:
            return username, fresh, expires_at_from(data.get("expires_in"))
    except InstagramError:
        logger.info("연결 시점 갱신은 건너뜁니다(24시간 미만이거나 갱신 불가) — 60일로 봅니다")
    return username, token, expires_at_from(60 * 24 * 3600)

def refresh_if_due() -> str:
    """저장해 둔 장기 토큰이 만료에 가까우면 미리 갱신한다. 갱신했으면 새 만료일을 돌려준다.

    왜 필요한가 — 대시보드에서 받은 토큰은 60일짜리다. 그냥 두면 60일 뒤에 사장님이 다시
    연결해야 하는데, 그 전에 한 번 갱신해 주면 계속 쓸 수 있다(Meta refresh_access_token:
    24시간 이상 지난 **장기** 토큰에만 동작하고, 갱신 시점부터 다시 60일).

    화면을 열 때와 게시 직전에 부른다 — 따로 도는 스케줄러 없이 쓰는 순간에 갱신한다.
    실패해도 조용히 넘어간다 — 아직 유효한 토큰이 있으니 게시를 막을 이유가 없다.
    """
    from app import models
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        row = db.get(models.InstagramAccount, 1)
        if not row or not row.access_token:
            return ""                      # 저장된 계정이 없다(.env 폴백은 우리가 갱신하지 않는다)
        left = days_left(row.expires_at)
        if left is None or left > REFRESH_BEFORE_DAYS:
            return ""                      # 만료일을 모르거나 아직 여유가 있다
        data = _api("GET", "refresh_access_token", grant_type="ig_refresh_token",
                    access_token=row.access_token)
        token = str(data.get("access_token") or "")
        if not token:
            return ""
        row.access_token = token
        row.expires_at = expires_at_from(data.get("expires_in"))
        db.commit()
        logger.info("인스타 토큰을 갱신했습니다 — 만료 %s", row.expires_at)
        return row.expires_at
    except Exception:
        logger.warning("인스타 토큰 갱신 실패 — 지금 토큰을 그대로 씁니다", exc_info=True)
        return ""
    finally:
        db.close()


def expires_at_from(expires_in) -> str:
    """응답의 남은 초 → 만료 예정일(YYYY-MM-DD). 값이 없으면 빈 문자열."""
    try:
        secs = int(expires_in)
    except (TypeError, ValueError):
        return ""
    return (dt.date.today() + dt.timedelta(seconds=secs)).isoformat()


def days_left(expires_at: str):
    """만료까지 남은 날짜. 모르면 None."""
    try:
        return (dt.date.fromisoformat(expires_at) - dt.date.today()).days
    except (TypeError, ValueError):
        return None


def account_name(token: str = "") -> str:
    """연결 확인용. 계정 이름이 돌아오면 토큰이 살아 있는 것이다.

    token 을 주면 그 토큰으로 확인한다 — 온보딩에서 **저장하기 전에** 값이 맞는지 보려고.
    """
    params = {"fields": "user_id,username"}
    if token:
        params["access_token"] = token
    return str(_api("GET", "me", **params).get("username") or "")


def to_feed_jpeg(src: Path) -> Path:
    """4:5 보다 긴 세로 이미지는 좌우에 흰 여백을 채워 4:5 로 맞추고 JPEG 로 저장한다.

    자르지 않고 여백을 넣는 이유: 네컷은 잘리면 컷 하나가 사라진다.
    """
    im = Image.open(src).convert("RGB")
    w, h = im.size
    if w / h < TARGET_RATIO:                      # 너무 길쭉하다 → 좌우에 여백
        new_w = int(round(h * TARGET_RATIO))
        canvas = Image.new("RGB", (new_w, h), "white")
        canvas.paste(im, ((new_w - w) // 2, 0))
        im = canvas
    elif w / h > 1.91:                            # 너무 납작하다 → 위아래에 여백
        new_h = int(round(w / 1.91))
        canvas = Image.new("RGB", (w, new_h), "white")
        canvas.paste(im, (0, (new_h - im.size[1]) // 2))
        im = canvas
    if im.width > 1440:                           # 인스타 권장 최대 폭
        im = im.resize((1440, int(im.height * 1440 / im.width)), Image.LANCZOS)
    out = settings.media_path / f"ig_{uuid.uuid4().hex}.jpg"
    im.save(out, "JPEG", quality=92)
    return out


def publish(poster: Path, caption: str) -> dict:
    """완성본 파일 + 캡션 → 실제 게시. {"media_id", "permalink", "image"} 를 돌려준다."""
    if not available():
        raise InstagramError(missing_reason())

    jpeg = to_feed_jpeg(poster)
    image_url = f"{settings.public_base_url.rstrip('/')}/api/media/{jpeg.name}"
    ig = creds()[0]

    created = _api("POST", f"{ig}/media", image_url=image_url, caption=caption or "")
    creation_id = created.get("id")
    if not creation_id:
        raise InstagramError("인스타그램이 게시 준비 번호를 주지 않았어요")

    # 인스타가 우리 이미지를 받아 가는 동안 기다린다. 바로 publish 하면 실패한다.
    for _ in range(POLL_TRIES):
        st = _api("GET", str(creation_id), fields="status_code,status").get("status_code")
        if st == "FINISHED":
            break
        if st == "ERROR":
            raise InstagramError("인스타그램이 이미지를 가져가지 못했어요 — 이미지 주소가 외부에서 열리는지 확인해 주세요")
        time.sleep(POLL_WAIT)
    else:
        raise InstagramError("인스타그램이 아직 이미지를 처리 중이에요. 잠시 뒤 다시 시도해 주세요")

    published = _api("POST", f"{ig}/media_publish", creation_id=creation_id)
    media_id = published.get("id")
    if not media_id:
        raise InstagramError("게시는 됐는데 게시물 번호를 못 받았어요 — 인스타그램 앱에서 확인해 주세요")

    permalink = ""
    try:
        permalink = str(_api("GET", str(media_id), fields="permalink").get("permalink") or "")
    except InstagramError:
        logger.warning("게시물 링크 조회 실패 (게시 자체는 성공)")   # 링크는 없어도 게시는 끝났다

    return {"media_id": str(media_id), "permalink": permalink, "image": f"/api/media/{jpeg.name}"}
