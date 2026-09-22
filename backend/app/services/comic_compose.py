"""완성본 한 장 만들기 — 네컷을 2×2로 붙이고 **대사를 그림에 굽는다.**

왜 필요한가. 화면의 말풍선은 프론트가 그림 위에 얹은 CSS 레이어다(ComicPanels.jsx).
보기엔 멀쩡한데 "이미지 저장"을 누르면 ComfyUI 원본을 그대로 받아서 **대사가 통째로
사라진다.** 사장님이 SNS에 올리는 건 대사 없는 그림 넉 장이 된다.

왜 ComfyUI가 아니라 여기인가. 팀이 ComfyUI에 만들어 둔 조립 워크플로가 있고
(`W7_assemble_korean`, `V3B_4koma_onegrid`) 레이아웃 수치는 그걸 그대로 따랐다 —
2×2 · 24px 검은 간격 · Pretendard-Bold. 다만 그 워크플로의 말풍선은
`ImagePadForOutpaint`로 컷 위에 흰 띠를 덧댄 **캡션 띠**다. 화면과 같은
**둥근 흰 박스 + 테두리 + 꼬리**를 그리는 노드가 ComfyUI에 없다.

그리고 여기서 하면 그림을 ComfyUI로 다시 올릴 일이 없다 — 넉 장은 이미
media/에 있다. 업로드·큐 대기·다운로드가 통째로 빠진다.

**말풍선 모양·자리는 ComicPanels.jsx와 맞춰 둔다.** 화면에서 본 것과 저장한 것이
다르면 그게 더 나쁘다. 홀수 컷은 왼쪽 위, 짝수 컷은 오른쪽 위, 폭은 최대 72%.
"""

import logging
import textwrap
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings

logger = logging.getLogger(__name__)

MEDIA_URL_PREFIX = "/api/media"

# 컷 사이 간격과 색 — V3B_4koma_onegrid 의 ImageStitch 와 같은 값이다.
GUTTER = 24
GUTTER_COLOR = (0, 0, 0)

# 말풍선 — ComicPanels.jsx 의 Bubble 과 같은 비율이다.
BUBBLE_MAX_W = 0.72      # 컷 폭의 72%
BUBBLE_MARGIN = 0.04     # 컷 가장자리에서 4%
BUBBLE_TOP = 0.03        # 위에서 3%
BUBBLE_PAD_X = 22
BUBBLE_PAD_Y = 14
BUBBLE_RADIUS = 18
BUBBLE_BORDER = 3
BUBBLE_BG = (255, 255, 255)
BUBBLE_FG = (17, 17, 17)
BUBBLE_LINE = (34, 34, 34)
TAIL_W = 26
TAIL_H = 20

# 한글이 되는 폰트만 고른다. 위에서부터 있는 것을 쓴다 —
# Pretendard 는 ComfyUI 쪽 폴더라 그 서비스가 걷히면 사라질 수 있어서, 시스템에
# 늘 있는 나눔을 뒤에 받쳐 둔다. 하나도 없으면 PIL 기본 폰트로 떨어지는데
# 그건 한글을 네모로 그리므로, 그때는 굽지 않고 실패로 돌려보낸다.
FONT_CANDIDATES = (
    "/home/sprint03/ComfyUI/fonts/Pretendard-Bold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",  # 맥에서 돌릴 때
)


def _font(size: int) -> ImageFont.FreeTypeFont | None:
    for path in FONT_CANDIDATES:
        if not Path(path).exists():
            continue
        try:
            return ImageFont.truetype(path, size)
        except OSError as exc:
            # 파일은 있는데 폰트로 못 읽는 경우(깨짐·권한). 다음 후보로 넘어가되
            # 조용히 넘기지는 않는다 — 나중에 "왜 나눔으로 나오지"를 못 찾는다.
            logger.warning("폰트를 읽지 못해 다음 후보로 갑니다: %s (%s)", path, type(exc).__name__)
    return None


def _wrap(text: str, font, draw: ImageDraw.ImageDraw, max_w: int) -> list[str]:
    """글자 폭을 재서 줄을 나눈다. 한국어는 띄어쓰기가 드물어 단어 단위로만 나누면
    한 줄이 통째로 넘치므로, 넘치면 글자 단위로 한 번 더 자른다."""
    lines: list[str] = []
    for chunk in textwrap.wrap(text, width=40) or [text]:
        line = ""
        for ch in chunk:
            if draw.textlength(line + ch, font=font) <= max_w:
                line += ch
            else:
                if line:
                    lines.append(line)
                line = ch
        if line:
            lines.append(line)
    return lines or [text]


def _draw_bubble(img: Image.Image, text: str, left_side: bool) -> None:
    """컷 한 장 위에 말풍선을 그린다. ComicPanels.jsx 의 Bubble 과 같은 자리·같은 모양."""
    text = (text or "").strip()
    if not text:
        return
    w, h = img.size
    draw = ImageDraw.Draw(img)

    size = max(20, int(w * 0.055))
    font = _font(size)
    if font is None:
        raise RuntimeError("한글 폰트를 찾지 못했습니다")

    max_text_w = int(w * BUBBLE_MAX_W) - BUBBLE_PAD_X * 2
    lines = _wrap(text, font, draw, max_text_w)
    line_h = int(size * 1.35)
    text_w = max(int(draw.textlength(ln, font=font)) for ln in lines)
    box_w = text_w + BUBBLE_PAD_X * 2
    box_h = line_h * len(lines) + BUBBLE_PAD_Y * 2

    margin = int(w * BUBBLE_MARGIN)
    x0 = margin if left_side else w - margin - box_w
    y0 = int(h * BUBBLE_TOP)

    draw.rounded_rectangle(
        (x0, y0, x0 + box_w, y0 + box_h),
        radius=BUBBLE_RADIUS, fill=BUBBLE_BG, outline=BUBBLE_LINE, width=BUBBLE_BORDER,
    )

    # 꼬리 — 박스 아래쪽에서 삼각형으로 내린다. 화면과 같이 왼쪽 풍선은 왼쪽,
    # 오른쪽 풍선은 오른쪽에 붙인다.
    tail_x = x0 + 30 if left_side else x0 + box_w - 30 - TAIL_W
    tail_y = y0 + box_h
    draw.polygon(
        [(tail_x, tail_y - BUBBLE_BORDER), (tail_x + TAIL_W, tail_y - BUBBLE_BORDER),
         (tail_x + (0 if left_side else TAIL_W), tail_y + TAIL_H)],
        fill=BUBBLE_BG, outline=BUBBLE_LINE,
    )
    # 꼬리를 그리며 같이 칠해진 박스 아래 테두리를 지운다 — 안 지우면 풍선 안에
    # 가로줄이 하나 생긴다.
    draw.line(
        [(tail_x + 2, tail_y - BUBBLE_BORDER), (tail_x + TAIL_W - 2, tail_y - BUBBLE_BORDER)],
        fill=BUBBLE_BG, width=BUBBLE_BORDER,
    )

    ty = y0 + BUBBLE_PAD_Y
    for line in lines:
        draw.text((x0 + BUBBLE_PAD_X, ty), line, font=font, fill=BUBBLE_FG)
        ty += line_h


def compose_poster(cut_images: list[Path], lines: list[str]) -> str:
    """네컷 + 대사 → 완성본 한 장. 돌려주는 값은 내려받을 URL이다.

    컷이 넷이 아니면(1컷짜리 인스타 게시물 등) 격자를 만들지 않고 그 장들만 세로로
    잇는다 — 2×2 는 4컷만화의 모양이지 모든 광고의 모양이 아니다.
    """
    if not cut_images:
        raise RuntimeError("붙일 그림이 없습니다")

    imgs = [Image.open(p).convert("RGB") for p in cut_images]
    # 홀수 컷은 왼쪽 위, 짝수 컷은 오른쪽 위 — ComicPanels.jsx 의 `cut.n % 2 === 1` 과 같다.
    # 다 같은 쪽에 두면 2×2 로 붙였을 때 풍선이 한 줄로 서서 눈이 지그재그로 안 움직인다.
    for i, (img, line) in enumerate(zip(imgs, lines)):
        _draw_bubble(img, line, left_side=(i % 2 == 0))

    # 컷마다 크기가 다를 수 있다(리롤·모델 교체). 첫 장에 맞춰 통일한다.
    cw, ch = imgs[0].size
    imgs = [im if im.size == (cw, ch) else im.resize((cw, ch)) for im in imgs]

    if len(imgs) == 4:
        cols, rows = 2, 2
    else:
        cols, rows = 1, len(imgs)

    W = cw * cols + GUTTER * (cols + 1)
    H = ch * rows + GUTTER * (rows + 1)
    poster = Image.new("RGB", (W, H), GUTTER_COLOR)
    for i, im in enumerate(imgs):
        r, c = divmod(i, cols)
        poster.paste(im, (GUTTER + c * (cw + GUTTER), GUTTER + r * (ch + GUTTER)))

    filename = f"{uuid.uuid4().hex}.png"
    poster.save(settings.media_path / filename, "PNG")
    return f"{MEDIA_URL_PREFIX}/{filename}"
