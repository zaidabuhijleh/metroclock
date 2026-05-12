import importlib
import math
import time
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

import config
import web_server
from core.widget import Widget
from widgets import icons


DOT_DIGITS = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "010", "100", "100"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
}


SEGMENT_MAP = {
    "0": {"a", "b", "c", "d", "e", "f"},
    "1": {"b", "c"},
    "2": {"a", "b", "g", "e", "d"},
    "3": {"a", "b", "c", "d", "g"},
    "4": {"f", "g", "b", "c"},
    "5": {"a", "f", "g", "c", "d"},
    "6": {"a", "f", "g", "e", "c", "d"},
    "7": {"a", "b", "c"},
    "8": {"a", "b", "c", "d", "e", "f", "g"},
    "9": {"a", "b", "c", "d", "f", "g"},
}


class ClockWidget(Widget):
    """Home clock with optional compact widget pane."""

    COLOR_BG = (0, 0, 0)
    COLOR_MAIN = (232, 238, 255)
    COLOR_ACCENT = (128, 186, 255)
    COLOR_ACCENT_2 = (255, 198, 96)
    COLOR_DIM = (88, 102, 132)
    COLOR_UP = (92, 226, 130)
    COLOR_DOWN = (239, 97, 97)
    COLOR_DIVIDER = (48, 62, 90)

    FACE_OPTIONS = {"digital_matrix", "digital_segment", "analog_ring", "analog_compass"}
    LAYOUT_OPTIONS = {"horizontal", "vertical"}
    WIDGET_SOURCES = {"metro", "weather", "flight", "sports", "stocks", "ambient"}

    def __init__(self, width, height, metro_widget, weather_widget, flight_widget, sports_widget, stocks_widget):
        super().__init__(width, height)
        self.metro = metro_widget
        self.weather = weather_widget
        self.flight = flight_widget
        self.sports = sports_widget
        self.stocks = stocks_widget

        self._metro_idx = 0
        self._stock_idx = 0
        self._last_widget_rotate = time.time()
        self._widget_rotate_seconds = 5.0

        self._ticker_offset = 0.0
        self._last_ticker_step = time.time()
        self._scroll_offsets = {}
        self._scroll_last_ts = {}

        try:
            self.font_tall = ImageFont.truetype(config.FONT_PATH_TALL, 10)
        except Exception:
            self.font_tall = ImageFont.load_default()
        try:
            self.font_small = ImageFont.truetype(config.FONT_PATH_SMALL, 6)
        except Exception:
            self.font_small = ImageFont.load_default()

    # --------------------------------------------------------------- config

    def _face(self):
        face = str(getattr(config, "CLOCK_FACE", "digital_matrix") or "digital_matrix").strip().lower()
        return face if face in self.FACE_OPTIONS else "digital_matrix"

    def _layout(self):
        layout = str(getattr(config, "CLOCK_WIDGET_LAYOUT", "horizontal") or "horizontal").strip().lower()
        return layout if layout in self.LAYOUT_OPTIONS else "horizontal"

    def _widget_source(self):
        source = str(getattr(config, "CLOCK_WIDGET_SOURCE", "weather") or "weather").strip().lower()
        return source if source in self.WIDGET_SOURCES else "weather"

    def _widget_source_secondary(self):
        source = str(getattr(config, "CLOCK_WIDGET_SOURCE_SECONDARY", "stocks") or "stocks").strip().lower()
        return source if source in self.WIDGET_SOURCES else "stocks"

    def _widget_count(self):
        try:
            count = int(getattr(config, "CLOCK_WIDGET_COUNT", 1))
        except Exception:
            count = 1
        return 2 if count >= 2 else 1

    def _use_24h(self):
        return bool(getattr(config, "CLOCK_USE_24H", False))

    # --------------------------------------------------------------- state

    def update(self):
        importlib.reload(config)

        if web_server.get_display_mode() != "clock_widget":
            return

        now = time.time()
        layout = self._layout()
        widget_count = self._widget_count()
        primary_req = self._widget_source()
        secondary_req = self._widget_source_secondary()

        sources_to_update = set()
        if layout == "vertical":
            # Focused side pane.
            sources_to_update.add(self._resolve_supported_source(primary_req, "vertical"))
            # Optional secondary horizontal strip in two-widget mode.
            if widget_count == 2:
                sources_to_update.add(self._resolve_supported_source(secondary_req, "horizontal"))
        else:
            sources_to_update.add(self._resolve_supported_source(primary_req, "horizontal"))
            if widget_count == 2:
                sources_to_update.add(self._resolve_supported_source(secondary_req, "horizontal"))

        if "metro" in sources_to_update:
            self.metro.update()
        if "weather" in sources_to_update:
            self.weather.update()
        if "flight" in sources_to_update:
            self.flight.update()
        if "sports" in sources_to_update:
            self.sports.update()
        if "stocks" in sources_to_update:
            self.stocks.update()
            # Compact clock views depend on 1D data for price + delta display.
            for sym in self._stock_symbols():
                key = (sym, "1D")
                if key in getattr(self.stocks, "cache", {}):
                    continue
                try:
                    self.stocks._fetch_chart(sym, "1D")
                except Exception:
                    pass

        if now - self._last_widget_rotate >= self._widget_rotate_seconds:
            trains = getattr(self.metro, "trains", []) or []
            if trains:
                self._metro_idx = (self._metro_idx + 1) % len(trains)

            symbols = self._stock_symbols()
            if symbols:
                self._stock_idx = (self._stock_idx + 1) % len(symbols)

            self._last_widget_rotate = now

    # --------------------------------------------------------------- draw

    def draw(self):
        self.canvas = Image.new("RGB", (self.width, self.height), self.COLOR_BG)
        draw = ImageDraw.Draw(self.canvas)

        mode = web_server.get_display_mode()
        if mode == "clock":
            face = self._render_clock_face(self.width, self.height, "full")
            self.canvas.paste(face, (0, 0))
            return self.canvas

        layout = self._layout()
        widget_count = self._widget_count()
        primary_req = self._widget_source()
        secondary_req = self._widget_source_secondary()

        if layout == "vertical":
            # Wider side pane than before for clearer focused widget rendering.
            side_w = int(round(self.width * 0.5))
            left_w = self.width - side_w
            side_source = self._resolve_supported_source(primary_req, "vertical")

            if widget_count == 2 and left_w >= 12 and self.height >= 12:
                # Left area becomes clock (top) + horizontal mini-widget (bottom).
                left_clock_h = max(1, min(self.height - 1, int(round(self.height * 2 / 3))))
                left_bottom_h = self.height - left_clock_h

                face = self._render_clock_face(left_w, left_clock_h, "vertical")
                self.canvas.paste(face, (0, 0))

                bottom_source = self._resolve_supported_source(secondary_req, "horizontal")
                self._draw_widget_region(
                    draw,
                    0,
                    left_clock_h,
                    left_w,
                    max(1, left_bottom_h),
                    bottom_source,
                    focused=False,
                )
            else:
                face = self._render_clock_face(left_w, self.height, "vertical")
                self.canvas.paste(face, (0, 0))

            self._draw_widget_region(
                draw,
                left_w,
                0,
                max(1, side_w),
                self.height,
                side_source,
                focused=True,
            )
        else:
            clock_h = max(1, min(self.height - 1, int(round(self.height * 2 / 3))))
            widget_h = self.height - clock_h

            face = self._render_clock_face(self.width, clock_h, "horizontal")
            self.canvas.paste(face, (0, 0))

            if widget_count == 2 and self.width >= 16:
                left_w = self.width // 2
                right_w = self.width - left_w
                source_a = self._resolve_supported_source(primary_req, "horizontal")
                source_b = self._resolve_supported_source(secondary_req, "horizontal")

                self._draw_widget_region(
                    draw,
                    0,
                    clock_h,
                    left_w,
                    max(1, widget_h),
                    source_a,
                    focused=False,
                )
                self._draw_widget_region(
                    draw,
                    left_w,
                    clock_h,
                    max(1, right_w),
                    max(1, widget_h),
                    source_b,
                    focused=False,
                )
            else:
                source = self._resolve_supported_source(primary_req, "horizontal")
                self._draw_widget_region(
                    draw,
                    0,
                    clock_h,
                    self.width,
                    max(1, widget_h),
                    source,
                    focused=False,
                )

        return self.canvas

    # --------------------------------------------------------------- clock faces

    def _render_clock_face(self, w, h, variant):
        img = Image.new("RGB", (max(1, w), max(1, h)), self.COLOR_BG)
        d = ImageDraw.Draw(img)
        face = self._face()

        try:
            if face == "digital_matrix":
                self._draw_face_digital_matrix(d, w, h, variant)
            elif face == "digital_segment":
                self._draw_face_digital_segment(d, w, h, variant)
            elif face == "analog_ring":
                self._draw_face_analog_ring(d, w, h, variant)
            else:
                self._draw_face_analog_compass(d, w, h, variant)
        except Exception:
            # Keep clock mode alive even if one face errors in an edge case.
            try:
                self._draw_face_digital_matrix(d, w, h, variant)
            except Exception:
                d.text((1, 1), self._time_text(False), font=self.font_small, fill=self.COLOR_MAIN)

        return img

    def _time_parts(self):
        now = datetime.now()
        hour = now.hour
        ampm = ""
        if not self._use_24h():
            ampm = "AM" if hour < 12 else "PM"
            hour = hour % 12 or 12
        return now, hour, ampm

    def _time_text(self, include_seconds=False):
        now, hour, _ = self._time_parts()
        if include_seconds:
            return f"{hour:02d}:{now.minute:02d}:{now.second:02d}"
        return f"{hour:02d}:{now.minute:02d}"

    def _draw_face_digital_matrix(self, draw, w, h, variant):
        now, hour, ampm = self._time_parts()
        text = f"{hour:02d}:{now.minute:02d}"

        columns = 0
        for ch in text:
            columns += 1 if ch == ":" else 3
            columns += 1
        columns -= 1

        rows = 5
        cell = max(1, min(w // max(1, columns), h // (rows + 2)))
        dot = max(1, cell - 1)
        total_w = columns * cell
        total_h = rows * cell
        x0 = max(0, (w - total_w) // 2)
        y0 = max(0, (h - total_h) // 2 - (1 if variant == "full" else 0))

        cursor = 0
        for ch in text:
            if ch == ":":
                cx = x0 + cursor * cell
                upper = y0 + cell
                lower = y0 + (rows - 2) * cell
                blink_on = (time.time() % 1.0) > 0.25
                if blink_on:
                    draw.rectangle((cx, upper, cx + dot - 1, upper + dot - 1), fill=self.COLOR_ACCENT_2)
                    draw.rectangle((cx, lower, cx + dot - 1, lower + dot - 1), fill=self.COLOR_ACCENT_2)
                cursor += 2
                continue

            glyph = DOT_DIGITS.get(ch, DOT_DIGITS["0"])
            for gy, row in enumerate(glyph):
                for gx, val in enumerate(row):
                    if val != "1":
                        continue
                    px = x0 + (cursor + gx) * cell
                    py = y0 + gy * cell
                    draw.rectangle((px, py, px + dot - 1, py + dot - 1), fill=self.COLOR_MAIN)
            cursor += 4

        if variant == "full" and h >= 28:
            date_label = now.strftime("%a %b %d").upper()
            dw = int(self.font_small.getlength(date_label))
            draw.text((max(0, (w - dw) // 2), h - 6), date_label, font=self.font_small, fill=self.COLOR_ACCENT)
            if ampm:
                draw.text((1, 1), ampm, font=self.font_small, fill=self.COLOR_ACCENT_2)

    def _draw_seven_seg_digit(self, draw, x, y, dw, dh, thickness, digit, on, off):
        segs = SEGMENT_MAP.get(digit, set())
        half = dh // 2

        def col(seg):
            return on if seg in segs else off

        # Horizontal segments
        draw.rectangle((x + thickness, y, x + dw - thickness - 1, y + thickness - 1), fill=col("a"))
        draw.rectangle((x + thickness, y + half - thickness // 2, x + dw - thickness - 1, y + half + thickness // 2 - 1), fill=col("g"))
        draw.rectangle((x + thickness, y + dh - thickness, x + dw - thickness - 1, y + dh - 1), fill=col("d"))

        # Vertical segments
        draw.rectangle((x, y + thickness, x + thickness - 1, y + half - 1), fill=col("f"))
        draw.rectangle((x + dw - thickness, y + thickness, x + dw - 1, y + half - 1), fill=col("b"))
        draw.rectangle((x, y + half, x + thickness - 1, y + dh - thickness - 1), fill=col("e"))
        draw.rectangle((x + dw - thickness, y + half, x + dw - 1, y + dh - thickness - 1), fill=col("c"))

    def _draw_face_digital_segment(self, draw, w, h, variant):
        now, hour, ampm = self._time_parts()
        time_text = f"{hour:02d}{now.minute:02d}"

        digit_count = 4
        colon_w = max(1, w // 40)
        spacing = max(1, w // 32)
        total_non_digit = colon_w + spacing * 3
        digit_w = max(4, (w - total_non_digit) // digit_count)
        digit_h = max(8, h - (10 if variant == "full" else 3))
        thickness = max(1, digit_w // 5)
        total_w = digit_w * digit_count + total_non_digit
        x = max(0, (w - total_w) // 2)
        y = max(0, (h - digit_h) // 2 - (1 if variant == "full" else 0))

        off = (18, 24, 36)

        for idx, ch in enumerate(time_text):
            self._draw_seven_seg_digit(draw, x, y, digit_w, digit_h, thickness, ch, self.COLOR_MAIN, off)
            x += digit_w
            if idx == 1:
                cx = x + spacing // 2
                blink_on = (time.time() % 1.0) > 0.25
                if blink_on:
                    draw.rectangle((cx, y + digit_h // 3, cx + colon_w - 1, y + digit_h // 3 + colon_w - 1), fill=self.COLOR_ACCENT_2)
                    draw.rectangle((cx, y + (digit_h * 2) // 3, cx + colon_w - 1, y + (digit_h * 2) // 3 + colon_w - 1), fill=self.COLOR_ACCENT_2)
                x += colon_w + spacing
            else:
                x += spacing

        if variant == "full" and h >= 28:
            sub = now.strftime("%a %m/%d").upper()
            sw = int(self.font_small.getlength(sub))
            draw.text(((w - sw) // 2, h - 6), sub, font=self.font_small, fill=self.COLOR_DIM)
            if ampm:
                draw.text((w - int(self.font_small.getlength(ampm)) - 1, 1), ampm, font=self.font_small, fill=self.COLOR_ACCENT_2)

    def _draw_analog_base(self, draw, w, h, ring_color):
        cx = w // 2
        cy = h // 2
        radius = max(5, min(w, h) // 2 - 2)
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=ring_color)
        return cx, cy, radius

    def _draw_clock_hands(self, draw, cx, cy, radius):
        now = datetime.now()
        sec = now.second + now.microsecond / 1_000_000.0
        minute = now.minute + sec / 60.0
        hour = (now.hour % 12) + minute / 60.0

        hour_angle = math.radians(hour * 30.0 - 90.0)
        min_angle = math.radians(minute * 6.0 - 90.0)
        sec_angle = math.radians(sec * 6.0 - 90.0)

        hx = int(cx + math.cos(hour_angle) * (radius * 0.55))
        hy = int(cy + math.sin(hour_angle) * (radius * 0.55))
        mx = int(cx + math.cos(min_angle) * (radius * 0.78))
        my = int(cy + math.sin(min_angle) * (radius * 0.78))
        sx = int(cx + math.cos(sec_angle) * (radius * 0.9))
        sy = int(cy + math.sin(sec_angle) * (radius * 0.9))

        draw.line((cx, cy, hx, hy), fill=self.COLOR_MAIN, width=2)
        draw.line((cx, cy, mx, my), fill=self.COLOR_ACCENT, width=1)
        draw.line((cx, cy, sx, sy), fill=self.COLOR_ACCENT_2, width=1)
        draw.point((cx, cy), fill=self.COLOR_MAIN)

    def _draw_face_analog_ring(self, draw, w, h, variant):
        cx, cy, radius = self._draw_analog_base(draw, w, h, self.COLOR_ACCENT)

        for i in range(60):
            angle = math.radians(i * 6 - 90)
            outer = radius
            inner = radius - (3 if i % 5 == 0 else 1)
            x1 = int(cx + math.cos(angle) * inner)
            y1 = int(cy + math.sin(angle) * inner)
            x2 = int(cx + math.cos(angle) * outer)
            y2 = int(cy + math.sin(angle) * outer)
            draw.line((x1, y1, x2, y2), fill=self.COLOR_DIM if i % 5 else self.COLOR_MAIN)

        self._draw_clock_hands(draw, cx, cy, radius - 1)

        if variant == "full" and h >= 28:
            now = datetime.now()
            d = now.strftime("%a").upper()
            draw.text((1, 1), d, font=self.font_small, fill=self.COLOR_DIM)

    def _draw_face_analog_compass(self, draw, w, h, variant):
        cx, cy, radius = self._draw_analog_base(draw, w, h, self.COLOR_DIM)

        # Cardinal marks
        marks = [("12", 0), ("3", 90), ("6", 180), ("9", 270)]
        for label, deg in marks:
            angle = math.radians(deg - 90)
            tx = int(cx + math.cos(angle) * (radius - 2))
            ty = int(cy + math.sin(angle) * (radius - 2))
            lw = int(self.font_small.getlength(label))
            draw.text((tx - lw // 2, ty - 3), label, font=self.font_small, fill=self.COLOR_DIM)

        # Inner crosshair
        draw.line((cx - radius + 2, cy, cx + radius - 2, cy), fill=(24, 30, 45))
        draw.line((cx, cy - radius + 2, cx, cy + radius - 2), fill=(24, 30, 45))

        self._draw_clock_hands(draw, cx, cy, radius - 2)
        draw.ellipse((cx - 1, cy - 1, cx + 1, cy + 1), fill=self.COLOR_ACCENT_2)

        if variant == "full" and h >= 28:
            t = self._time_text(include_seconds=False)
            tw = int(self.font_small.getlength(t))
            draw.text((max(0, (w - tw) // 2), h - 7), t, font=self.font_small, fill=self.COLOR_DIM)

    # --------------------------------------------------------------- widget region

    def _resolve_supported_source(self, requested, slot):
        source = str(requested or "").strip().lower()
        if source not in self.WIDGET_SOURCES:
            source = "weather"

        if slot == "vertical":
            # Focused side pane: weather + stocks only.
            return source if source in {"stocks", "weather"} else "weather"

        # Horizontal mini pane: support all except ambient.
        if source == "ambient":
            return "weather"
        return source

    def _draw_widget_region(self, draw, x, y, w, h, source, focused=False):
        if w <= 0 or h <= 0:
            return

        try:
            if source == "metro":
                self._draw_widget_metro(draw, x, y, w, h)
                return
            if source == "weather":
                self._draw_widget_weather(draw, x, y, w, h, focused=focused)
                return
            if source == "stocks":
                self._draw_widget_stocks(draw, x, y, w, h, focused=focused)
                return
            if source == "flight":
                self._draw_widget_flight(draw, x, y, w, h)
                return
            if source == "sports":
                self._draw_widget_sports(draw, x, y, w, h)
                return

            txt = self._fit_text(source.upper(), max(0, w - 2), self.font_small)
            draw.text((x + 1, y + max(0, (h - 6) // 2)), txt, font=self.font_small, fill=self.COLOR_DIM)
        except Exception:
            fallback = self._fit_text("WIDGET ERR", max(0, w - 2), self.font_small)
            draw.text((x + 1, y + max(0, (h - 6) // 2)), fallback, font=self.font_small, fill=self.COLOR_DOWN)

    def _current_metro_station_label(self):
        system = str(getattr(config, "METRO_SYSTEM", "wmata") or "wmata").strip().lower()
        if system == "nyc":
            raw = str(getattr(config, "NYC_STOP_IDS", "") or "")
            first = raw.split(",")[0].strip().upper() if raw else ""
            if hasattr(self.metro, "_strip_nyc_stop_id"):
                try:
                    stripped = self.metro._strip_nyc_stop_id(first)
                except Exception:
                    stripped = first
            else:
                stripped = first
            name_map = getattr(self.metro, "_nyc_stop_name_map", {}) or {}
            return str(name_map.get(first) or name_map.get(stripped) or stripped or "NYC")

        if system == "ttc":
            sid = str(getattr(config, "TTC_STATION_ID", "") or "").strip()
            return sid.replace("_", " ").upper() if sid else "TTC"

        code = str(getattr(config, "WMATA_STATION_CODE", "") or "").split(",")[0].strip().upper()
        return code or "WMATA"

    def _draw_scrolling_text_clipped(
        self,
        x,
        y,
        w,
        h,
        text,
        color,
        key,
        speed=16.0,
        always_scroll=False,
        wrap=True,
        align="center",
    ):
        if w <= 1 or h <= 1:
            return

        txt = str(text or "").strip()
        if not txt:
            return

        region = Image.new("RGB", (w, h), self.COLOR_BG)
        rd = ImageDraw.Draw(region)
        text_w = int(self.font_small.getlength(txt))
        y_text = max(0, (h - 6) // 2)

        visible_w = max(1, w - 2)
        if not always_scroll and text_w <= visible_w:
            if align == "left":
                text_x = 1
            elif align == "right":
                text_x = max(1, w - text_w - 1)
            else:
                text_x = max(1, (w - text_w) // 2)
            rd.text((text_x, y_text), txt, font=self.font_small, fill=color)
            self.canvas.paste(region, (x, y))
            return

        now = time.time()
        last_ts = self._scroll_last_ts.get(key, now)
        dt = now - last_ts
        self._scroll_last_ts[key] = now
        if dt < 0 or dt > 0.6:
            dt = 0.05

        gap = 10
        cycle = text_w + gap
        offset = self._scroll_offsets.get(key, 0.0)
        if wrap:
            offset = (offset + dt * speed) % cycle
        else:
            max_offset = max(0.0, float(text_w - visible_w))
            offset = min(max_offset, offset + dt * speed)
        self._scroll_offsets[key] = offset

        if wrap:
            start_x = w - int(offset)
            rd.text((start_x, y_text), txt, font=self.font_small, fill=color)
            rd.text((start_x - cycle, y_text), txt, font=self.font_small, fill=color)
        else:
            start_x = 1 - int(offset)
            rd.text((start_x, y_text), txt, font=self.font_small, fill=color)
        self.canvas.paste(region, (x, y))

    def _draw_widget_metro(self, draw, x, y, w, h):
        trains = getattr(self.metro, "trains", []) or []
        if not trains:
            draw.text((x + 1, y + max(0, (h - 6) // 2)), "NO TRAINS", font=self.font_small, fill=self.COLOR_DIM)
            return

        row = trains[self._metro_idx % len(trains)]
        line = str(row.get("Line", "--")).upper()
        mins = str(row.get("Min", "--"))
        dest = str(row.get("Destination", "Train") or "Train")

        line_color = self.metro._line_color(line) if hasattr(self.metro, "_line_color") else self.COLOR_ACCENT
        line_label = (line[:2] or "?").upper()
        line_label_w = int(self.font_small.getlength(line_label))

        # Fixed left segment for line ID, like the main metro row "icon + static line".
        left_w = min(max(8, line_label_w + 4), max(8, w // 3))
        left_w = min(left_w, max(1, w - 6))
        right_w = max(1, w - left_w)

        line_x = x + max(1, (left_w - line_label_w) // 2)
        line_y = y + max(0, (h - 6) // 2)
        draw.text((line_x, line_y), line_label, font=self.font_small, fill=line_color)

        mins_label = f"{mins}M" if mins.isdigit() else mins
        scroll_text = f"{dest.upper()} {mins_label}".strip()
        scroll_speed = float(getattr(self.metro, "scroll_speed", 20))
        self._draw_scrolling_text_clipped(
            x + left_w,
            y,
            right_w,
            h,
            scroll_text,
            self.COLOR_MAIN,
            key=f"metro-mini:{line}:{dest}:{mins}",
            speed=scroll_speed,
            always_scroll=False,
            wrap=False,
            align="left",
        )

    def _weather_data(self):
        preview = web_server.get_weather_preview()
        if preview:
            return web_server.preview_weather_data(preview, config.WEATHER_UNITS)
        return getattr(self.weather, "data", None)

    def _weather_condition_key(self, weather_data):
        if hasattr(self.weather, "_resolve_condition_key"):
            try:
                return self.weather._resolve_condition_key(weather_data)
            except Exception:
                pass
        return "clear_day"

    def _weather_label(self, key):
        if hasattr(self.weather, "_format_condition_label"):
            try:
                return self.weather._format_condition_label(key)
            except Exception:
                pass
        return "Weather"

    def _weather_icon_image(self, condition_key, frame_index, out_w, out_h):
        pixels, palette = icons.get_frame(condition_key, frame_index)
        icon_img = Image.new("RGB", (icons.WIDTH, icons.HEIGHT), (0, 0, 0))
        px = icon_img.load()
        for i, color_idx in enumerate(pixels):
            if color_idx == 0:
                continue
            xx = i % icons.WIDTH
            yy = i // icons.WIDTH
            px[xx, yy] = palette.get(color_idx, (255, 255, 255))
        return icon_img.resize((max(1, out_w), max(1, out_h)), Image.NEAREST)

    def _draw_widget_weather(self, draw, x, y, w, h, focused=False):
        data = self._weather_data()
        if not data:
            draw.text((x + 1, y + max(0, (h - 6) // 2)), "WEATHER", font=self.font_small, fill=self.COLOR_DIM)
            return

        temp = round(data["main"]["temp"])
        key = self._weather_condition_key(data)
        label = self._weather_label(key).upper()

        if focused:
            icon_h = min(14, h // 2 + 2)
            icon_w = min(w - 2, 12)
            icon = self._weather_icon_image(key, getattr(self.weather, "anim_frame", 0), icon_w, icon_h)
            self.canvas.paste(icon, (x + max(0, (w - icon_w) // 2), y + 1))

            temp_text = f"{temp}\N{DEGREE SIGN}"
            tw = int(self.font_tall.getlength(temp_text))
            draw.text((x + max(0, (w - tw) // 2), y + icon_h + 1), temp_text, font=self.font_tall, fill=self.COLOR_MAIN)

            if h >= 24:
                lbl = self._fit_text(label, max(0, w - 2), self.font_small)
                lw = int(self.font_small.getlength(lbl))
                draw.text((x + max(0, (w - lw) // 2), y + h - 7), lbl, font=self.font_small, fill=self.COLOR_ACCENT)
            return

        text = f"{temp}\N{DEGREE SIGN} {label}"
        self._draw_scrolling_text_clipped(x, y, w, h, text, self.COLOR_MAIN, key=f"weather:{temp}:{label}", speed=14.0)

    def _stock_symbols(self):
        if hasattr(self.stocks, "_symbols"):
            try:
                return self.stocks._symbols()
            except Exception:
                pass
        return ["AAPL", "TSLA", "NVDA", "SPY"]

    def _stock_data(self, symbol, timeframe="1D"):
        cache = getattr(self.stocks, "cache", {})
        exact = cache.get((symbol, timeframe))
        if exact:
            return exact
        for (sym, _tf), data in cache.items():
            if sym == symbol and data:
                return data
        return None

    def _draw_widget_stocks(self, draw, x, y, w, h, focused=False):
        symbols = self._stock_symbols()
        if not symbols:
            draw.text((x + 1, y + max(0, (h - 6) // 2)), "NO STOCKS", font=self.font_small, fill=self.COLOR_DIM)
            return

        if focused:
            symbol = symbols[self._stock_idx % len(symbols)]
            data = self._stock_data(symbol, "1D")
            draw.text((x + max(0, (w - int(self.font_tall.getlength(symbol))) // 2), y + 1), symbol, font=self.font_tall, fill=self.COLOR_MAIN)
            if not data or data.get("last_price") is None:
                draw.text((x + max(0, (w - int(self.font_small.getlength("..."))) // 2), y + h - 8), "...", font=self.font_small, fill=self.COLOR_DIM)
                return

            last = data.get("last_price")
            prev = data.get("prev_close")
            change = self.stocks._change(last, prev) if hasattr(self.stocks, "_change") else 0.0
            pct = self.stocks._fmt_pct(last, prev, signed=False) if hasattr(self.stocks, "_fmt_pct") else "--%"
            price = self.stocks._fmt_price(last) if hasattr(self.stocks, "_fmt_price") else str(last)
            color = self.COLOR_UP if change >= 0 else self.COLOR_DOWN

            p_fit = self._fit_text(price, max(0, w - 2), self.font_small)
            pct_fit = self._fit_text(pct, max(0, w - 2), self.font_small)
            draw.text((x + max(0, (w - int(self.font_small.getlength(p_fit))) // 2), y + 14), p_fit, font=self.font_small, fill=self.COLOR_MAIN)
            draw.text((x + max(0, (w - int(self.font_small.getlength(pct_fit))) // 2), y + h - 8), pct_fit, font=self.font_small, fill=color)
            return

        # Horizontal split stock ticker (mini).
        parts = []
        for sym in symbols:
            data = self._stock_data(sym, "1D")
            if not data or data.get("last_price") is None:
                continue
            last = data.get("last_price")
            prev = data.get("prev_close")
            price = self.stocks._fmt_price(last) if hasattr(self.stocks, "_fmt_price") else str(last)
            pct = self.stocks._fmt_pct(last, prev, signed=False) if hasattr(self.stocks, "_fmt_pct") else "--%"
            parts.append(f"{sym} {price} {pct}")

        if not parts:
            draw.text((x + 1, y + max(0, (h - 6) // 2)), "STOCKS LOADING", font=self.font_small, fill=self.COLOR_DIM)
            return

        ticker = "   ".join(parts)
        self._draw_scrolling_text_clipped(x, y, w, h, ticker, self.COLOR_UP, key=f"stocks:{ticker}", speed=18.0)

    def _draw_widget_flight(self, draw, x, y, w, h):
        data = getattr(self.flight, "data", None)
        if not data:
            txt = str(getattr(self.flight, "status_text", "FLIGHT")).upper()
            draw.text((x + 1, y + max(0, (h - 6) // 2)), self._fit_text(txt, max(0, w - 2), self.font_small), font=self.font_small, fill=self.COLOR_DIM)
            return

        flight_no = str((data.get("flight") or {}).get("iata") or getattr(config, "FLIGHT_NUMBER", "FLIGHT")).upper()
        status = str(data.get("flight_status", "") or "").upper()
        text = f"{flight_no} {status}"
        self._draw_scrolling_text_clipped(x, y, w, h, text, self.COLOR_MAIN, key=f"flight:{text}", speed=14.0)

    def _draw_widget_sports(self, draw, x, y, w, h):
        games = getattr(self.sports, "games", []) or []
        if not games:
            draw.text((x + 1, y + max(0, (h - 6) // 2)), "NO GAMES", font=self.font_small, fill=self.COLOR_DIM)
            return

        idx = getattr(self.sports, "current_game_index", 0) % len(games)
        game = games[idx]
        away = game.get("away", {})
        home = game.get("home", {})
        status = self.sports._status_text(game) if hasattr(self.sports, "_status_text") else ""
        text = f"{away.get('abbr', 'AWY')} {away.get('score', 0)}-{home.get('score', 0)} {home.get('abbr', 'HME')} {status}"
        self._draw_scrolling_text_clipped(x, y, w, h, text, self.COLOR_MAIN, key=f"sports:{text}", speed=14.0)

    # --------------------------------------------------------------- utils

    def _fit_text(self, text, max_width, font):
        if not text:
            return ""
        txt = str(text)
        if int(font.getlength(txt)) <= max_width:
            return txt
        while txt and int(font.getlength(txt + "...")) > max_width:
            txt = txt[:-1]
        return (txt + "...") if txt else ""
