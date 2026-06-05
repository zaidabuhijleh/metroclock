from PIL import Image, ImageDraw, ImageFont

import config
import config_manager
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
        config_manager.reload_config()
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

    def _timer_strip_image(self, timer_text, color):
        text = str(timer_text or "")
        if ":" not in text:
            return None
        mins, secs = text.split(":", 1)
        mins = mins.strip()
        secs = secs.strip()
        if not mins or not secs:
            return None

        mins_w = int(self.font_tall.getlength(mins))
        secs_w = int(self.font_tall.getlength(secs))
        gap_left = 0
        gap_right = 1
        strip_h = 10
        strip_w = max(1, mins_w + gap_left + 1 + gap_right + secs_w)
        strip = Image.new("RGB", (strip_w, strip_h), self.COLOR_BG)
        d = ImageDraw.Draw(strip)

        x = 0
        d.text((x, 0), mins, font=self.font_tall, fill=color)
        x += mins_w + gap_left
        d.point((x, 3), fill=color)
        d.point((x, 7), fill=color)
        x += 1 + gap_right
        d.text((x, 0), secs, font=self.font_tall, fill=color)
        return strip

    def _draw_timer(self, draw, timer_text, y, color, scale=1):
        strip = self._timer_strip_image(timer_text, color)
        if strip is None:
            tw = int(self.font_tall.getlength(str(timer_text or "")))
            draw.text((max(0, (self.width - tw) // 2), y), str(timer_text or ""), font=self.font_tall, fill=color)
            return

        target = strip
        if int(scale) > 1:
            target = strip.resize((strip.width * int(scale), strip.height * int(scale)), Image.NEAREST)
        x = max(0, (self.width - target.width) // 2)
        self.canvas.paste(target, (x, y))

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
            if running:
                self._draw_timer(draw, display_txt, y=9, color=self.COLOR_TEXT, scale=2)
            else:
                draw.text(((self.width - display_w) // 2, 12), display_txt, font=self.font_tall, fill=self.COLOR_TEXT)
            return self.canvas

        if running:
            self._draw_timer(draw, display_txt, y=9, color=self.COLOR_TEXT, scale=1)
        else:
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
