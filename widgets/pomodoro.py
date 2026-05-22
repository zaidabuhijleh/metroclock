import importlib

from PIL import Image, ImageDraw, ImageFont

import config
import web_server
from core.widget import Widget


class PomodoroWidget(Widget):
    """Standalone Pomodoro timer widget."""

    COLOR_BG = (0, 0, 0)
    COLOR_TEXT = (236, 244, 252)
    COLOR_DIM = (110, 132, 162)
    COLOR_BORDER = (52, 70, 96)
    COLOR_FILL = (86, 208, 132)

    PHASE_STYLES = {
        "focus": {"label": "FOCUS", "color": (255, 86, 86)},
        "short_break": {"label": "SHORT BREAK", "color": (84, 208, 242)},
        "long_break": {"label": "LONG BREAK", "color": (120, 236, 140)},
    }

    def __init__(self, width, height):
        super().__init__(width, height)
        self.state = None
        try:
            self.font_tall = ImageFont.truetype(config.FONT_PATH_TALL, 10)
        except Exception:
            self.font_tall = ImageFont.load_default()
        try:
            self.font_small = ImageFont.truetype(config.FONT_PATH_SMALL, 6)
        except Exception:
            self.font_small = ImageFont.load_default()

    def update(self):
        importlib.reload(config)
        self.state = web_server.get_pomodoro_state()

    def _fit_text(self, text, max_width, font):
        txt = str(text or "")
        if not txt:
            return ""
        if int(font.getlength(txt)) <= max_width:
            return txt
        while txt and int(font.getlength(txt + "...")) > max_width:
            txt = txt[:-1]
        return (txt + "...") if txt else ""

    def _timer_text(self, remaining_seconds):
        total = max(0, int(remaining_seconds or 0))
        minutes = total // 60
        seconds = total % 60
        return f"{minutes:02d}:{seconds:02d}"

    def draw(self):
        self.canvas = Image.new("RGB", (self.width, self.height), self.COLOR_BG)
        draw = ImageDraw.Draw(self.canvas)

        state = self.state or web_server.get_pomodoro_state() or {}
        phase = str(state.get("phase", "focus"))
        style = self.PHASE_STYLES.get(phase, self.PHASE_STYLES["focus"])
        phase_color = style["color"]

        timer_txt = self._timer_text(state.get("remaining_seconds", 0))
        timer_w = int(self.font_tall.getlength(timer_txt))
        draw.text(((self.width - timer_w) // 2, 9), timer_txt, font=self.font_tall, fill=self.COLOR_TEXT)

        phase_txt = style["label"]
        phase_w = int(self.font_small.getlength(phase_txt))
        draw.text(((self.width - phase_w) // 2, 1), phase_txt, font=self.font_small, fill=phase_color)

        progress = float(state.get("progress", 0.0) or 0.0)
        progress = max(0.0, min(1.0, progress))
        bar_x = 2
        bar_y = 20
        bar_w = max(8, self.width - 4)
        bar_h = 6
        draw.rectangle((bar_x, bar_y, bar_x + bar_w - 1, bar_y + bar_h - 1), outline=self.COLOR_BORDER, fill=self.COLOR_BG)
        inner_w = max(0, bar_w - 2)
        fill_w = int(round(inner_w * progress))
        if fill_w > 0:
            draw.rectangle(
                (bar_x + 1, bar_y + 1, bar_x + fill_w, bar_y + bar_h - 2),
                fill=self.COLOR_FILL,
            )

        running = bool(state.get("running", False))
        status_txt = "RUNNING" if running else "PAUSED"
        cycle_position = int(state.get("cycle_position", 1) or 1)
        long_every = max(1, int(state.get("long_break_every", 4) or 4))
        cycle_txt = f"{cycle_position}/{long_every}"
        done_txt = f"DONE {int(state.get('completed_focus_sessions', 0) or 0)}"

        draw.text((1, 27), self._fit_text(status_txt, 24, self.font_small), font=self.font_small, fill=self.COLOR_DIM)

        cycle_w = int(self.font_small.getlength(cycle_txt))
        done_w = int(self.font_small.getlength(done_txt))
        draw.text((max(0, (self.width - cycle_w) // 2), 27), cycle_txt, font=self.font_small, fill=phase_color)
        draw.text((max(0, self.width - done_w - 1), 27), done_txt, font=self.font_small, fill=self.COLOR_DIM)

        return self.canvas
