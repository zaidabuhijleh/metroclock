from __future__ import annotations

from typing import Iterable, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

import config


Color = Tuple[int, int, int]


DEFAULT_STATUS_COLORS: Sequence[Color] = (
    (255, 80, 60),
    (255, 210, 80),
    (120, 220, 255),
)


def render_status_frame(
    width: int,
    height: int,
    lines: Iterable[str],
    colors: Sequence[Color] = DEFAULT_STATUS_COLORS,
) -> Image.Image:
    image = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = _load_font()

    visible_lines = [str(line or "").upper()[:16] for line in lines][:3]
    while len(visible_lines) < 3:
        visible_lines.append("")

    y_positions = _line_positions(height)
    for idx, text in enumerate(visible_lines):
        if not text:
            continue
        color = colors[idx % len(colors)] if colors else (255, 255, 255)
        _draw_centered(draw, font, text, y_positions[idx], color, width)
    return image


def _load_font():
    try:
        return ImageFont.truetype(config.FONT_PATH_SMALL, config.FONT_SIZE_SMALL)
    except Exception:
        return ImageFont.load_default()


def _line_positions(height: int):
    if height >= 32:
        return [2, 12, 22]
    step = max(6, height // 3)
    return [0, min(height - 6, step), min(height - 6, step * 2)]


def _draw_centered(draw, font, text: str, y: int, color: Color, canvas_width: int):
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        left = bbox[0]
    except Exception:
        text_width = int(font.getlength(text)) if hasattr(font, "getlength") else len(text) * 4
        left = 0
    x = max(0, (canvas_width - text_width) // 2) - left
    draw.text((x, y), text, font=font, fill=color)
