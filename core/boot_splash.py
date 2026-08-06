from __future__ import annotations

from typing import Sequence, Tuple

from PIL import Image, ImageDraw


Color = Tuple[int, int, int]


METROCLOCK_MARK_COLORS: Sequence[Color] = (
    (221, 47, 69),
    (255, 152, 29),
    (7, 136, 200),
    (0, 157, 91),
    (248, 204, 24),
)


def render_boot_splash(
    width: int,
    height: int,
    colors: Sequence[Color] = METROCLOCK_MARK_COLORS,
    background: Color = (0, 0, 0),
) -> Image.Image:
    image = Image.new("RGB", (width, height), background)
    if width <= 0 or height <= 0 or not colors:
        return image

    draw = ImageDraw.Draw(image)
    count = len(colors)
    radius = max(2, int(round(min(height * 0.19, width / 12.8))))
    gap = max(1, int(round(radius * 0.4)))
    total_width = count * radius * 2 + (count - 1) * gap

    left = max(0, (width - total_width) // 2)
    center_y = height // 2
    step = radius * 2 + gap

    for index, color in enumerate(colors):
        center_x = left + radius + index * step
        draw.ellipse(
            (
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
            ),
            fill=color,
        )

    return image
