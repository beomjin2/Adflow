"""네컷 굽기 — 말풍선·입간판을 PNG 에 그리고 2×2 로 합친다 (PIL).

왜 코드로 그리나: 그림 모델(Anima)은 한글을 못 쓴다 — 09-22 실측 8장 모두 한글 모양 낙서. 영어는 거의 되지만
가게 정보는 한글이라 코드가 한글 폰트로 얹는다. 3배 크게 그려 줄이면 글자 테두리가 또렷하다.
- board(): 마지막 컷 왼쪽 아래 A-보드에 가게 정보(오늘의 빵·수량·영업시간·주소). 그 컷은 캐릭터를 오른쪽에 두고 뽑는다.
- bubble(): 위쪽 귀퉁이 말풍선, 캐릭터 반대편.
- compose(): 4장 → 2×2 한 장.
폰트: settings.comic_font_bold / comic_font_regular. 없으면 Windows 맑은 고딕 → PIL 기본(한글 깨짐, 경고).
"""
from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings

logger = logging.getLogger(__name__)

W, H = 832, 1216
RECT = (int(W * 0.03), int(H * 0.62), int(W * 0.40), int(H * 0.97))   # 입간판 자리 = 왼쪽 아래
_FALLBACKS_BOLD = ["C:/Windows/Fonts/malgunbd.ttf", "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
                   "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"]
_FALLBACKS_REG = ["C:/Windows/Fonts/malgun.ttf", "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                  "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]


def _font_path(bold: bool) -> str | None:
    cands = ([settings.comic_font_bold] if bold else [settings.comic_font_regular]) + (_FALLBACKS_BOLD if bold else _FALLBACKS_REG)
    for c in cands:
        if c and Path(c).is_file():
            return c
    logger.warning("한글 폰트를 못 찾았습니다 — 말풍선·입간판 글자가 깨집니다 (COMIC_FONT_BOLD 설정)")
    return None


def _font(bold: bool, size: int):
    p = _font_path(bold)
    return ImageFont.truetype(p, size) if p else ImageFont.load_default()


def _fit(d, text, bold, max_w, start, min_size=16):
    s = start
    while s > min_size:
        f = _font(bold, s)
        if d.textlength(text, font=f) <= max_w:
            return f
        s -= 2
    return _font(bold, min_size)


def board_lines(store: dict, prods: list[dict]) -> list[str]:
    """입간판 글 — 오늘의 빵 / 첫 생산 기록 / 영업시간 / 주소(시·구 제외). 빈 칸은 뺀다."""
    lines = ["오늘의 빵"]
    for p in prods[:1]:
        if p.get("name"):
            lines.append(f"{p['name']} {p.get('qty') or ''}".strip())
    hours = (store.get("hours") or "").split(",")[0].strip()
    if hours:
        lines.append(hours)
    addr = (store.get("address") or "").strip()
    if addr:
        parts = addr.split()
        lines.append(" ".join(parts[2:]) if len(parts) > 2 else addr)
    return lines


def board(im: Image.Image, lines: list[str]) -> Image.Image:
    """왼쪽 아래 A-보드 + 굵은 글자(3배 슈퍼샘플링·외곽선)."""
    S = 3
    im = im.convert("RGBA")
    if im.size != (W, H):
        im = im.resize((W, H), Image.LANCZOS)
    L = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    X0, Y0, X1, Y1 = [v * S for v in RECT]; bw, bh = X1 - X0, Y1 - Y0
    d.polygon([(X0 + 30, Y1 + 30), (X1 + 30, Y1 + 30), (X1 - 18, Y0 + 30), (X0 + 48, Y0 + 30)], fill=(0, 0, 0, 90))
    d.polygon([(X0, Y1), (X1, Y1), (X1 - 48, Y0), (X0 + 48, Y0)], fill=(92, 58, 30, 255))
    n = 42
    d.polygon([(X0 + n, Y1 - n), (X1 - n, Y1 - n), (X1 - 48 - n * 0.6, Y0 + n), (X0 + 48 + n * 0.6, Y0 + n)], fill=(28, 42, 36, 255))
    yy = Y0 + n + int(bh * 0.06)
    for i, t in enumerate(lines[:4]):
        f = _fit(d, t, True, bw - 2 * n - int(bw * 0.16), int(bh * (0.125 if i == 0 else 0.10)))
        tw = d.textlength(t, font=f)
        d.text((X0 + (bw - tw) / 2, yy), t, font=f, fill=(255, 252, 240, 255), stroke_width=max(2, int(bh * 0.006)), stroke_fill=(20, 30, 26, 255))
        yy += int(bh * 0.17)
    return Image.alpha_composite(im, L.resize((W, H), Image.LANCZOS)).convert("RGB")


def bubble(im: Image.Image, text: str, side: str) -> Image.Image:
    """말풍선을 PNG 에 굽는다 — 위쪽 귀퉁이, 캐릭터 반대편. side='left'|'right'."""
    if not (text or "").strip():
        return im.convert("RGB")
    S = 3
    im = im.convert("RGBA")
    if im.size != (W, H):
        im = im.resize((W, H), Image.LANCZOS)
    L = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    maxw = int(W * S * 0.62); f = _fit(d, text, True, maxw, int(H * S * 0.034), 30)
    words, lines, cur = text.split(" "), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if d.textlength(t, font=f) <= maxw:
            cur = t
        else:
            lines.append(cur); cur = w_
    if cur:
        lines.append(cur)
    lh = int(f.size * 1.35); tw = max(d.textlength(l, font=f) for l in lines)
    pad = int(W * S * 0.022); bw, bh = int(tw + 2 * pad), int(lh * len(lines) + 2 * pad * 0.8)
    x0 = int(W * S * 0.04) if side == "left" else W * S - int(W * S * 0.04) - bw; y0 = int(H * S * 0.03)
    d.rounded_rectangle((x0 + 6, y0 + 8, x0 + bw + 6, y0 + bh + 8), 30, fill=(0, 0, 0, 60))
    d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), 30, fill=(255, 255, 255, 255), outline=(34, 34, 34, 255), width=6)
    tx = x0 + int(bw * 0.25) if side == "left" else x0 + int(bw * 0.75)
    d.polygon([(tx - 26, y0 + bh - 2), (tx + 26, y0 + bh - 2), (tx, y0 + bh + 44)], fill=(255, 255, 255, 255), outline=(34, 34, 34, 255))
    d.line((tx - 26, y0 + bh - 2, tx + 26, y0 + bh - 2), fill=(255, 255, 255, 255), width=8)
    yy = y0 + int(pad * 0.8)
    for l in lines:
        d.text((x0 + pad, yy), l, font=f, fill=(17, 17, 17, 255)); yy += lh
    return Image.alpha_composite(im, L.resize((W, H), Image.LANCZOS)).convert("RGB")


def bubble_side(position: str | None, n: int) -> str:
    """캐릭터가 왼쪽이면 말풍선은 오른쪽. 위치를 모르면 홀수 컷 왼쪽."""
    if position == "왼쪽":
        return "right"
    if position == "오른쪽":
        return "left"
    return "left" if n % 2 == 1 else "right"


def compose(panels: list[Image.Image], gap: int = 24) -> Image.Image:
    """4장 → 2×2. 3장이면 아래 오른쪽이 빈다."""
    comic = Image.new("RGB", (W * 2 + gap * 3, H * 2 + gap * 3), (245, 240, 230))
    for j, p in enumerate(panels[:4]):
        comic.paste(p.convert("RGB").resize((W, H)), (gap + (j % 2) * (W + gap), gap + (j // 2) * (H + gap)))
    return comic
