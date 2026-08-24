from PIL import Image, ImageDraw, ImageFont

import config
from core.boot_splash import METROCLOCK_MARK_COLORS


WHITE = (255, 255, 255)


class DeviceMessageScreen:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        try:
            self.font = ImageFont.truetype(config.FONT_PATH_SMALL, config.FONT_SIZE_SMALL)
        except Exception:
            self.font = ImageFont.load_default()

    def render(self, lines):
        image = Image.new("RGB", (self.width, self.height), (0, 0, 0))
        draw = ImageDraw.Draw(image)
        self._draw_mark(draw)

        visible_lines = [str(line or "").upper()[:16] for line in lines][:3]
        while len(visible_lines) < 3:
            visible_lines.append("")

        for index, text in enumerate(visible_lines):
            if text:
                self._draw_centered(draw, text, 11 + index * 7)
        return image

    def _draw_mark(self, draw):
        count = len(METROCLOCK_MARK_COLORS)
        radius = 2
        gap = 1
        total_width = count * radius * 2 + (count - 1) * gap
        left = max(0, (self.width - total_width) // 2)
        center_y = 5
        for index, color in enumerate(METROCLOCK_MARK_COLORS):
            center_x = left + radius + index * (radius * 2 + gap)
            draw.ellipse(
                (
                    center_x - radius,
                    center_y - radius,
                    center_x + radius,
                    center_y + radius,
                ),
                fill=color,
            )

    def _draw_centered(self, draw, text, y):
        try:
            bbox = draw.textbbox((0, 0), text, font=self.font)
            width = bbox[2] - bbox[0]
            left = bbox[0]
        except Exception:
            width = int(self.font.getlength(text)) if hasattr(self.font, "getlength") else len(text) * 4
            left = 0
        x = max(0, (self.width - width) // 2) - left
        draw.text((x, y), text, font=self.font, fill=WHITE)
