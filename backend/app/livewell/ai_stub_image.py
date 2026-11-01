"""Local concept stub — produces a reviewable before/after board without a GPU provider.

When JarvisLabs / RunPod is not configured, this still completes the visualization
pipeline so assessors can review, approve, and attach concept images to reports.
"""

from __future__ import annotations

import io
from typing import Sequence

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - optional until pillow is installed
    Image = None  # type: ignore[assignment, misc]
    ImageDraw = None  # type: ignore[assignment, misc]
    ImageFont = None  # type: ignore[assignment, misc]


DISCLOSURE = (
    "CONCEPT STUB — illustrative only. Not a photo-real GPU render. "
    "Final recommendations require assessor review."
)


def _load_font(size: int):
    if ImageFont is None:
        return None
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        try:
            return ImageFont.truetype("arial.ttf", size)
        except OSError:
            return ImageFont.load_default()


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def build_local_stub_concept(
    source_bytes: bytes,
    *,
    room_type: str,
    package_level: str,
    modifications: Sequence[str] | None = None,
    width: int = 1024,
    height: int = 1024,
) -> tuple[bytes, str, bool]:
    """Return (png_bytes, content_type, used_pillow_board).

    If Pillow is unavailable, returns the original image bytes as a pass-through
    stub so the job lifecycle still reaches needs_review.
    """
    mods = [m.strip() for m in (modifications or []) if m and str(m).strip()]
    if Image is None:
        # Pass-through: still a completable stub for review/report wiring.
        ctype = "image/png" if source_bytes[:8].startswith(b"\x89PNG") else "image/jpeg"
        if source_bytes[:2] == b"\xff\xd8":
            ctype = "image/jpeg"
        return source_bytes, ctype, False

    try:
        src = Image.open(io.BytesIO(source_bytes)).convert("RGB")
    except Exception:
        src = Image.new("RGB", (max(320, width // 2), max(320, height // 2)), (40, 70, 80))

    board_w = max(640, int(width) or 1024)
    board_h = max(480, int(height) or 1024)
    board = Image.new("RGB", (board_w, board_h), (245, 241, 232))
    draw = ImageDraw.Draw(board)

    title_font = _load_font(28)
    body_font = _load_font(18)
    small_font = _load_font(14)

    header_h = 72
    draw.rectangle((0, 0, board_w, header_h), fill=(13, 110, 110))
    draw.text(
        (24, 18),
        "LiveWell360 · Proposed room concept (local stub)",
        fill=(255, 255, 255),
        font=title_font,
    )

    footer_h = 56
    draw.rectangle((0, board_h - footer_h, board_w, board_h), fill=(20, 58, 69))
    for i, line in enumerate(_wrap(draw, DISCLOSURE, small_font, board_w - 48)):
        draw.text((24, board_h - footer_h + 10 + i * 16), line, fill=(232, 217, 168), font=small_font)

    gutter = 20
    mid = board_w // 2
    panel_top = header_h + gutter
    panel_bottom = board_h - footer_h - gutter
    panel_h = max(120, panel_bottom - panel_top)
    left_box = (gutter, panel_top, mid - gutter // 2, panel_top + panel_h)
    right_box = (mid + gutter // 2, panel_top, board_w - gutter, panel_top + panel_h)

    def _fit(img: Image.Image, box: tuple[int, int, int, int]) -> None:
        x0, y0, x1, y1 = box
        bw, bh = max(1, x1 - x0), max(1, y1 - y0)
        fitted = img.copy()
        fitted.thumbnail((bw, bh), Image.Resampling.LANCZOS)
        ox = x0 + (bw - fitted.width) // 2
        oy = y0 + (bh - fitted.height) // 2
        board.paste(fitted, (ox, oy))
        draw.rectangle(box, outline=(20, 58, 69), width=2)

    _fit(src, left_box)
    draw.text((left_box[0] + 8, left_box[1] + 8), "BEFORE", fill=(20, 58, 69), font=body_font)

    # Proposed panel: same photo with teal wash + labels (GPU will replace later).
    proposed = src.copy().convert("RGBA")
    wash = Image.new("RGBA", proposed.size, (13, 110, 110, 70))
    proposed = Image.alpha_composite(proposed, wash).convert("RGB")
    _fit(proposed, right_box)
    draw.text(
        (right_box[0] + 8, right_box[1] + 8),
        f"PROPOSED · {package_level.upper()} · {room_type.upper()}",
        fill=(255, 255, 255),
        font=body_font,
    )

    label_y = right_box[1] + 40
    if not mods:
        mods = ["Approved assessment modifications (see improvement plan)"]
    for mod in mods[:6]:
        for line in _wrap(draw, f"• {mod}", small_font, right_box[2] - right_box[0] - 24):
            draw.text((right_box[0] + 12, label_y), line, fill=(255, 255, 255), font=small_font)
            label_y += 18
            if label_y > right_box[3] - 24:
                break
        if label_y > right_box[3] - 24:
            break

    out = io.BytesIO()
    board.save(out, format="PNG", optimize=True)
    return out.getvalue(), "image/png", True
