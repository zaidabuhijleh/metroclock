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
    COLOR_TASK = (170, 206, 248)

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
        layout = str(state.get("layout", "mode_time_task") or "mode_time_task").strip().lower()

        running = bool(state.get("running", False))
        display_txt = self._timer_text(state.get("remaining_seconds", 0)) if running else "PAUSED"
        display_w = int(self.font_tall.getlength(display_txt))

        phase_txt = style["label"]
        phase_w = int(self.font_small.getlength(phase_txt))
        draw.text(((self.width - phase_w) // 2, 1), phase_txt, font=self.font_small, fill=phase_color)

        if layout == "mode_time":
            draw.text(((self.width - display_w) // 2, 12), display_txt, font=self.font_tall, fill=self.COLOR_TEXT)
            return self.canvas

        draw.text(((self.width - display_w) // 2, 9), display_txt, font=self.font_tall, fill=self.COLOR_TEXT)

        task = str(state.get("current_task", "") or "").strip()
        if task:
            task_txt = self._fit_text(task.upper(), max(0, self.width - 2), self.font_small)
            task_w = int(self.font_small.getlength(task_txt))
            draw.text((max(0, (self.width - task_w) // 2), 24), task_txt, font=self.font_small, fill=self.COLOR_TASK)
        else:
            empty_txt = "NO TASK"
            empty_w = int(self.font_small.getlength(empty_txt))
            draw.text((max(0, (self.width - empty_w) // 2), 24), empty_txt, font=self.font_small, fill=self.COLOR_DIM)

        return self.canvas
