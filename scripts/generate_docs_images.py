"""
Generate PNG assets for README (no Cairo/SVG dependency).
Run from repo root: python scripts/generate_docs_images.py
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images"

# Theme
BG = (3, 7, 18)
CARD = (17, 24, 39)
BORDER = (30, 41, 59)
FG = (248, 250, 252)
MUTED = (148, 163, 184)
PRIMARY = (16, 185, 129)
SECONDARY = (99, 102, 241)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    windir = os.environ.get("WINDIR", "C:\\Windows")
    candidates = [
        os.path.join(windir, "Fonts", "segoeuib.ttf" if bold else "segoeui.ttf"),
        os.path.join(windir, "Fonts", "arialbd.ttf" if bold else "arial.ttf"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                pass
    return ImageFont.load_default()


def linear_gradient_h(
    draw: ImageDraw.ImageDraw, x0: int, y0: int, x1: int, y1: int, c0: tuple[int, int, int], c1: tuple[int, int, int]
) -> None:
    w = x1 - x0
    if w <= 0:
        return
    for i in range(w):
        t = i / (w - 1) if w > 1 else 0
        r = int(c0[0] + (c1[0] - c0[0]) * t)
        g = int(c0[1] + (c1[1] - c0[1]) * t)
        b = int(c0[2] + (c1[2] - c0[2]) * t)
        draw.line([(x0 + i, y0), (x0 + i, y1)], fill=(r, g, b))


def deepshield_mark() -> None:
    w, h = 1040, 240
    im = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle([4, 4, w - 5, h - 5], radius=28, outline=BORDER, width=2)
    # Shield blob (simplified)
    sx, sy = 48, 40
    shield_w, shield_h = 88, 100
    pts = [
        (sx + shield_w // 2, sy),
        (sx + shield_w, sy + 28),
        (sx + shield_w, sy + shield_h - 24),
        (sx + shield_w // 2, sy + shield_h),
        (sx, sy + shield_h - 24),
        (sx, sy + 28),
    ]
    for y in range(sy, sy + shield_h):
        x0 = sx + int((y - sy) * 0.12)
        x1 = sx + shield_w - int((y - sy) * 0.12)
        t = (y - sy) / max(shield_h - 1, 1)
        c = (
            int(PRIMARY[0] + (SECONDARY[0] - PRIMARY[0]) * t),
            int(PRIMARY[1] + (SECONDARY[1] - PRIMARY[1]) * t),
            int(PRIMARY[2] + (SECONDARY[2] - PRIMARY[2]) * t),
        )
        draw.line([(x0, y), (x1, y)], fill=c)
    draw.polygon(pts, outline=(15, 23, 42))
    title = _font(44, True)
    sub = _font(22, False)
    small = _font(18, False)
    draw.text((168, 52), "DeepShield", fill=FG, font=title)
    draw.text((168, 112), "Media authenticity · Face-centric AI screening", fill=MUTED, font=small)
    OUT.mkdir(parents=True, exist_ok=True)
    im.save(OUT / "deepshield-mark.png", "PNG", optimize=True)
    print("Wrote", OUT / "deepshield-mark.png")


def pipeline_overview() -> None:
    w, h = 1440, 320
    im = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(im)
    title_f = _font(20, True)
    box_f = _font(22, True)
    sub_f = _font(18, False)
    foot = _font(18, False)
    draw.text((32, 28), "INFERENCE PIPELINE (SIMPLIFIED)", fill=MUTED, font=title_f)

    boxes = [
        (32, 72, 176, 176, "Upload", "Video / Image"),
        (232, 72, 376, 176, "Face detect", "MTCNN"),
        (432, 72, 576, 176, "Classifier", "EfficientNet-B0"),
        (632, 72, 776, 176, "Aggregate", "Robust score"),
        (832, 72, 976, 176, "Explain", "Grad-CAM"),
    ]
    for x0, y0, x1, y1, t1, t2 in boxes:
        draw.rounded_rectangle([x0, y0, x1, y1], radius=16, fill=CARD, outline=BORDER, width=2)
        bb = draw.textbbox((0, 0), t1, font=box_f)
        draw.text((x0 + (x1 - x0 - (bb[2] - bb[0])) // 2, y0 + 28), t1, fill=FG, font=box_f)
        bb2 = draw.textbbox((0, 0), t2, font=sub_f)
        draw.text((x0 + (x1 - x0 - (bb2[2] - bb2[0])) // 2, y0 + 72), t2, fill=MUTED, font=sub_f)

    # Arrows between boxes
    gaps = [(208, 232), (408, 432), (608, 632), (808, 832)]
    for xa, xb in gaps:
        y = 120
        linear_gradient_h(draw, xa, y - 2, xb, y + 2, PRIMARY, SECONDARY)
        draw.polygon([(xb - 8, y - 6), (xb, y), (xb - 8, y + 6)], fill=SECONDARY)

    draw.text(
        (32, 252),
        "Optional early-exit and configurable frame sampling reduce cost on long clips.",
        fill=(100, 116, 139),
        font=foot,
    )
    im.save(OUT / "pipeline-overview.png", "PNG", optimize=True)
    print("Wrote", OUT / "pipeline-overview.png")


def ui_preview() -> None:
    w, h = 1280, 720
    im = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle([8, 8, w - 9, h - 9], radius=28, outline=BORDER, width=2)
    # Header
    draw.rectangle([8, 8, w - 8, 88], fill=(3, 7, 18))
    draw.ellipse([36, 36, 60, 60], fill=(16, 185, 129))
    draw.ellipse([40, 40, 56, 56], fill=PRIMARY)
    f_head = _font(28, True)
    f_sub = _font(20, False)
    f_label = _font(18, False)
    f_big = _font(40, True)
    f_mono = _font(48, True)
    draw.text((80, 38), "DeepShield", fill=FG, font=f_head)
    bw, bh = 120, 40
    bx = w - 140
    draw.rounded_rectangle([bx, 32, bx + bw, 32 + bh], radius=10, fill=CARD, outline=BORDER)
    bb = draw.textbbox((0, 0), "Analyzer", font=f_sub)
    draw.text((bx + (bw - (bb[2] - bb[0])) // 2, 40), "Analyzer", fill=MUTED, font=f_sub)

    draw.text((48, 128), "WORKSPACE", fill=MUTED, font=f_label)
    draw.text((48, 168), "Results", fill=FG, font=_font(36, True))

    # Score card
    cx0, cy0 = 48, 220
    cx1, cy1 = w - 48, 520
    draw.rounded_rectangle([cx0, cy0, cx1, cy1], radius=22, fill=CARD, outline=BORDER, width=2)
    draw.text((72, 252), "AUTHENTICITY SIGNAL", fill=MUTED, font=f_label)
    draw.text((72, 292), "Consistent with authentic capture", fill=FG, font=f_big)
    bar_y = 380
    bar_h = 16
    draw.rounded_rectangle([72, bar_y, cx1 - 72, bar_y + bar_h], radius=6, fill=(30, 41, 59))
    linear_gradient_h(draw, 72, bar_y, 72 + 280, bar_y + bar_h, PRIMARY, SECONDARY)
    draw.text((cx1 - 120, 320), "24%", fill=PRIMARY, font=f_mono)
    draw.text((cx1 - 120, 400), "P(fake)", fill=(100, 116, 139), font=f_sub)

    # Thumbnails
    tx = 72
    for _ in range(3):
        draw.rounded_rectangle([tx, 440, tx + 100, 500], radius=8, fill=(30, 41, 59), outline=BORDER)
        tx += 116

    draw.text((48, h - 56), "Conceptual UI preview · Next.js dashboard", fill=(71, 85, 105), font=f_label)
    im.save(OUT / "ui-preview.png", "PNG", optimize=True)
    print("Wrote", OUT / "ui-preview.png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    deepshield_mark()
    pipeline_overview()
    ui_preview()


if __name__ == "__main__":
    main()
