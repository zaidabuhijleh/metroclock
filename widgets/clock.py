import importlib
import math
import time
from dataclasses import dataclass
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


@dataclass
class ClockTheme:
    bg: tuple[int, int, int]
    primary: tuple[int, int, int]
    accent: tuple[int, int, int]
    accent_2: tuple[int, int, int]
    dim: tuple[int, int, int]


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

    FONT_STYLE_OPTIONS = {"matrix", "segment"}
    CLOCK_SIZE_OPTIONS = (0.5, 0.75, 1.0)
    LAYOUT_OPTIONS = {"horizontal", "vertical"}
    WIDGET_SOURCES = {"metro", "weather", "flight", "sports", "stocks", "ambient"}
    MINI_WIDGET_MIN_FRACTION = {
        "metro": 0.50,
        "stocks": 0.50,
        "weather": 0.33,
        "flight": 0.33,
        "sports": 0.40,
        "ambient": 0.33,
    }

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

    def _font_style(self):
        style = str(getattr(config, "CLOCK_FONT_STYLE", "matrix") or "matrix").strip().lower()
        return style if style in self.FONT_STYLE_OPTIONS else "matrix"

    def _clock_size(self):
        raw = getattr(config, "CLOCK_SIZE", getattr(config, "CLOCK_SIZE_SCALE", 1.0))
        try:
            value = float(raw)
        except Exception:
            value = 1.0
        best = self.CLOCK_SIZE_OPTIONS[0]
        best_dist = abs(value - best)
        for option in self.CLOCK_SIZE_OPTIONS:
            dist = abs(value - option)
            if dist < best_dist:
                best = option
                best_dist = dist
        return best

    def _effective_clock_size(self):
        # Clock+widget mode always uses small clock sizing for readability balance.
        if web_server.get_display_mode() == "clock_widget":
            return 0.5
        return self._clock_size()

    def _show_date(self):
        return bool(getattr(config, "CLOCK_SHOW_DATE", True))

    def _show_ampm(self):
        return bool(getattr(config, "CLOCK_SHOW_AMPM", True))

    def _parse_color_override(self, raw):
        txt = str(raw or "").strip()
        if not txt:
            return None
        if txt.startswith("#"):
            txt = txt[1:]
        if len(txt) != 6:
            return None
        try:
            return (int(txt[0:2], 16), int(txt[2:4], 16), int(txt[4:6], 16))
        except Exception:
            return None

    def _clock_theme(self):
        return ClockTheme(
            bg=self._parse_color_override(getattr(config, "CLOCK_COLOR_BG", "")) or self.COLOR_BG,
            primary=self._parse_color_override(getattr(config, "CLOCK_COLOR_PRIMARY", "")) or self.COLOR_MAIN,
            accent=self._parse_color_override(getattr(config, "CLOCK_COLOR_ACCENT", "")) or self.COLOR_ACCENT,
            accent_2=self._parse_color_override(getattr(config, "CLOCK_COLOR_ACCENT_2", "")) or self.COLOR_ACCENT_2,
            dim=self._parse_color_override(getattr(config, "CLOCK_COLOR_DIM", "")) or self.COLOR_DIM,
        )

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
        theme = self._clock_theme()
        self.canvas = Image.new("RGB", (self.width, self.height), theme.bg)
        draw = ImageDraw.Draw(self.canvas)

        mode = web_server.get_display_mode()
        if mode == "clock":
            face = self._render_clock_face(self.width, self.height, "full", theme)
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
                split_ratio = 2 / 3
                left_clock_h = max(1, min(self.height - 1, int(round(self.height * split_ratio))))
                left_bottom_h = self.height - left_clock_h

                face = self._render_clock_face(left_w, left_clock_h, "vertical_split_top", theme)
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
                face = self._render_clock_face(left_w, self.height, "vertical_focus", theme)
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

            face = self._render_clock_face(self.width, clock_h, "horizontal", theme)
            self.canvas.paste(face, (0, 0))

            if widget_count == 2 and self.width >= 16:
                source_a = self._resolve_supported_source(primary_req, "horizontal")
                source_b = self._resolve_supported_source(secondary_req, "horizontal")
                left_w, right_w = self._two_widget_widths(self.width, source_a, source_b)

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

    def _render_clock_face(self, w, h, variant, theme):
        img = Image.new("RGB", (max(1, w), max(1, h)), theme.bg)
        d = ImageDraw.Draw(img)
        style = self._font_style()

        try:
            renderer = {
                "matrix": self._draw_face_digital_matrix,
                "segment": self._draw_face_digital_segment,
            }.get(style, self._draw_face_digital_matrix)
            renderer(d, w, h, variant, theme)
        except Exception:
            # Keep clock mode alive even if one face errors in an edge case.
            try:
                self._draw_face_digital_matrix(d, w, h, variant, theme)
            except Exception:
                d.text((1, 1), self._time_text(False), font=self.font_small, fill=theme.primary)

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

    def _overlay_band_height(self, h, variant, enabled):
        if not enabled:
            return 0
        if variant not in {"full", "vertical_focus"}:
            return 0
        if h < 20:
            return 0
        return 6

    def _clock_layout_metrics(self, w, h, variant):
        style = self._font_style()
        size = self._effective_clock_size()
        show_top_overlay = self._show_ampm() and (not self._use_24h())
        show_bottom_overlay = self._show_date()
        top_band = self._overlay_band_height(h, variant, show_top_overlay)
        bottom_band = self._overlay_band_height(h, variant, show_bottom_overlay)

        clock_top = top_band
        clock_bottom = max(clock_top + 1, h - bottom_band)
        available_h = max(6, clock_bottom - clock_top)
        available_w = max(12, w - 2)

        spacing = 1
        colon_w = 1 if style == "matrix" else 2
        slot_w = max(2, (available_w - colon_w - (spacing * 3)) // 4)
        slot_h = max(6, available_h)

        raw_digit_w = max(2, int(round(slot_w * size)))
        raw_digit_h = max(6, int(round(slot_h * size)))
        min_digit_w = 3 if style == "matrix" else 4
        min_digit_h = 6 if style == "matrix" else 8

        digit_w = min(slot_w, max(min_digit_w if slot_w >= min_digit_w else slot_w, raw_digit_w))
        digit_h = min(slot_h, max(min_digit_h if slot_h >= min_digit_h else slot_h, raw_digit_h))

        total_w = digit_w * 4 + colon_w + (spacing * 3)
        x0 = max(0, (w - total_w) // 2)
        y0 = clock_top + max(0, (available_h - digit_h) // 2)
        return {
            "size": size,
            "spacing": spacing,
            "colon_w": colon_w,
            "digit_w": digit_w,
            "digit_h": digit_h,
            "x0": x0,
            "y0": y0,
            "top_band": top_band,
            "bottom_band": bottom_band,
            "clock_top": clock_top,
            "clock_bottom": clock_bottom,
        }

    def _draw_clock_overlays(self, draw, w, h, variant, ampm, theme, date_text, metrics):
        if self._show_date() and metrics["bottom_band"] > 0:
            dw = int(self.font_small.getlength(date_text))
            date_y = h - metrics["bottom_band"] + max(0, (metrics["bottom_band"] - 6) // 2)
            draw.text((max(0, (w - dw) // 2), date_y), date_text, font=self.font_small, fill=theme.accent)

        if self._show_ampm() and ampm and not self._use_24h() and metrics["top_band"] > 0:
            aw = int(self.font_small.getlength(ampm))
            ampm_y = max(0, (metrics["top_band"] - 6) // 2)
            draw.text((max(0, (w - aw) // 2), ampm_y), ampm, font=self.font_small, fill=theme.accent_2)

    def _draw_face_digital_matrix(self, draw, w, h, variant, theme):
        now, hour, ampm = self._time_parts()
        digits = f"{hour:02d}{now.minute:02d}"
        metrics = self._clock_layout_metrics(w, h, variant)
        cell = max(1, min(metrics["digit_w"] // 3, metrics["digit_h"] // 5))
        dot = max(1, cell - 1)
        total_h = cell * 5
        y0 = max(0, metrics["y0"] + (metrics["digit_h"] - total_h) // 2)
        blink_on = (time.time() % 1.0) > 0.25

        for digit_index, ch in enumerate(digits):
            digit_left = metrics["x0"] + digit_index * (metrics["digit_w"] + metrics["spacing"])
            if digit_index >= 2:
                digit_left += metrics["colon_w"] + metrics["spacing"]
            glyph = DOT_DIGITS.get(ch, DOT_DIGITS["0"])
            gx_off = max(0, (metrics["digit_w"] - cell * 3) // 2)
            for gy, row in enumerate(glyph):
                for gx, val in enumerate(row):
                    if val != "1":
                        continue
                    px = digit_left + gx_off + gx * cell
                    py = y0 + gy * cell
                    draw.rectangle((px, py, px + dot - 1, py + dot - 1), fill=theme.primary)

        colon_left = metrics["x0"] + 2 * (metrics["digit_w"] + metrics["spacing"])
        colon_x = colon_left + max(0, (metrics["colon_w"] - dot) // 2)
        if blink_on:
            draw.rectangle((colon_x, y0 + cell, colon_x + dot - 1, y0 + cell + dot - 1), fill=theme.accent_2)
            draw.rectangle((colon_x, y0 + (cell * 3), colon_x + dot - 1, y0 + (cell * 3) + dot - 1), fill=theme.accent_2)

        self._draw_clock_overlays(
            draw,
            w,
            h,
            variant,
            ampm,
            theme,
            now.strftime("%a %b %d").upper(),
            metrics,
        )

    def _draw_seven_seg_digit(self, draw, x, y, dw, dh, thickness, digit, on, off):
        segs = SEGMENT_MAP.get(digit, set())
        thickness = max(1, min(thickness, max(1, min(dw // 3, dh // 4))))
        half = dh // 2
        mid_top = max(y + thickness, y + half - thickness // 2)
        mid_bottom = min(y + dh - thickness - 1, mid_top + thickness - 1)
        upper_end = max(y + thickness, mid_top - 1)
        lower_start = min(y + dh - thickness - 1, mid_bottom + 1)

        def col(seg):
            return on if seg in segs else off

        # Horizontal segments
        draw.rectangle((x + thickness, y, x + dw - thickness - 1, y + thickness - 1), fill=col("a"))
        draw.rectangle((x + thickness, mid_top, x + dw - thickness - 1, mid_bottom), fill=col("g"))
        draw.rectangle((x + thickness, y + dh - thickness, x + dw - thickness - 1, y + dh - 1), fill=col("d"))

        # Vertical segments
        if upper_end >= y + thickness:
            draw.rectangle((x, y + thickness, x + thickness - 1, upper_end), fill=col("f"))
            draw.rectangle((x + dw - thickness, y + thickness, x + dw - 1, upper_end), fill=col("b"))
        if y + dh - thickness - 1 >= lower_start:
            draw.rectangle((x, lower_start, x + thickness - 1, y + dh - thickness - 1), fill=col("e"))
            draw.rectangle((x + dw - thickness, lower_start, x + dw - 1, y + dh - thickness - 1), fill=col("c"))

    def _draw_face_digital_segment(self, draw, w, h, variant, theme):
        now, hour, ampm = self._time_parts()
        digits = f"{hour:02d}{now.minute:02d}"
        metrics = self._clock_layout_metrics(w, h, variant)
        off = tuple(max(0, c // 4) for c in theme.dim)
        thickness = max(1, metrics["digit_w"] // 5)

        for digit_index, ch in enumerate(digits):
            x = metrics["x0"] + digit_index * (metrics["digit_w"] + metrics["spacing"])
            if digit_index >= 2:
                x += metrics["colon_w"] + metrics["spacing"]
            self._draw_seven_seg_digit(
                draw,
                x,
                metrics["y0"],
                metrics["digit_w"],
                metrics["digit_h"],
                thickness,
                ch,
                theme.primary,
                off,
            )

        blink_on = (time.time() % 1.0) > 0.25
        if blink_on:
            colon_left = metrics["x0"] + 2 * (metrics["digit_w"] + metrics["spacing"])
            cx = colon_left + max(0, (metrics["colon_w"] - 1) // 2)
            dot = max(1, metrics["colon_w"])
            draw.rectangle(
                (cx, metrics["y0"] + metrics["digit_h"] // 3, cx + dot - 1, metrics["y0"] + metrics["digit_h"] // 3 + dot - 1),
                fill=theme.accent_2,
            )
            draw.rectangle(
                (cx, metrics["y0"] + (metrics["digit_h"] * 2) // 3, cx + dot - 1, metrics["y0"] + (metrics["digit_h"] * 2) // 3 + dot - 1),
                fill=theme.accent_2,
            )

        self._draw_clock_overlays(
            draw,
            w,
            h,
            variant,
            ampm,
            theme,
            now.strftime("%a %m/%d").upper(),
            metrics,
        )

    # --------------------------------------------------------------- widget region

    def _resolve_supported_source(self, requested, slot):
        source = str(requested or "").strip().lower()
        if source not in self.WIDGET_SOURCES:
            source = "weather"

        if slot == "vertical":
            # Focused side pane: weather + stocks + sports.
            return source if source in {"stocks", "weather", "sports"} else "weather"

        # Horizontal mini pane: support all except ambient.
        if source == "ambient":
            return "weather"
        return source

    def _mini_widget_min_fraction(self, source):
        key = str(source or "").strip().lower()
        raw = self.MINI_WIDGET_MIN_FRACTION.get(key, 0.33)
        try:
            value = float(raw)
        except Exception:
            value = 0.33
        return max(0.2, min(0.8, value))

    def _two_widget_widths(self, total_w, source_a, source_b):
        if total_w <= 2:
            left_w = max(1, total_w // 2)
            return left_w, max(1, total_w - left_w)

        frac_a = self._mini_widget_min_fraction(source_a)
        frac_b = self._mini_widget_min_fraction(source_b)

        min_a = max(1, int(math.ceil(total_w * frac_a)))
        min_b = max(1, int(math.ceil(total_w * frac_b)))

        if min_a + min_b > total_w:
            # If both minimums cannot fit, keep relative intent and normalize.
            total_min = float(min_a + min_b)
            left_w = int(round(total_w * (min_a / total_min)))
            left_w = max(1, min(total_w - 1, left_w))
            return left_w, total_w - left_w

        left_w = min_a
        right_w = min_b
        remaining = total_w - left_w - right_w
        if remaining <= 0:
            return left_w, right_w

        # Give spare room to whichever widget benefits more from width.
        if frac_a > frac_b:
            left_w += remaining
        elif frac_b > frac_a:
            right_w += remaining
        else:
            left_w += remaining // 2
            right_w += remaining - (remaining // 2)

        return left_w, right_w

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
                self._draw_widget_sports(draw, x, y, w, h, focused=focused)
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
        step = max(0.0, dt * speed)
        # Keep per-frame movement bounded so transient frame drops do not
        # cause large multi-pixel jumps that look choppy on the matrix.
        step = min(step, 1.0)
        if wrap:
            offset = (offset + step) % cycle
        else:
            max_offset = max(0.0, float(text_w - visible_w))
            offset = min(max_offset, offset + step)
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

        unit_raw = str(getattr(config, "WEATHER_UNITS", "metric") or "metric").strip().lower()
        unit_suffix = "F" if unit_raw in {"imperial", "f", "fahrenheit"} else "C"
        text = f"{temp}\N{DEGREE SIGN}{unit_suffix}"
        fit = self._fit_text(text, max(0, w - 2), self.font_small)
        draw.text((x + max(1, (w - int(self.font_small.getlength(fit))) // 2), y + max(0, (h - 6) // 2)), fit, font=self.font_small, fill=self.COLOR_MAIN)

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

    def _draw_widget_sports(self, draw, x, y, w, h, focused=False):
        games = getattr(self.sports, "games", []) or []
        if not games:
            draw.text((x + 1, y + max(0, (h - 6) // 2)), "NO GAMES", font=self.font_small, fill=self.COLOR_DIM)
            return

        idx = getattr(self.sports, "current_game_index", 0) % len(games)
        game = games[idx]
        away = game.get("away", {})
        home = game.get("home", {})

        if focused:
            status = self.sports._status_text(game) if hasattr(self.sports, "_status_text") else "LIVE"
            status_fit = self._fit_text(status, max(1, w - 2), self.font_small)
            status_w = int(self.font_small.getlength(status_fit))
            draw.text((x + max(0, (w - status_w) // 2), y + 1), status_fit, font=self.font_small, fill=self.COLOR_DIM)

            status_band_h = 8
            row_gap = 2
            row_h = max(8, (h - status_band_h - row_gap) // 2)
            away_y = y + status_band_h
            home_y = away_y + row_h
            bar_w = 2

            def draw_team_row(team, other, side, row_y):
                team_color = tuple(team.get("color") or self.COLOR_ACCENT)
                draw.rectangle((x, row_y + 1, x + bar_w - 1, min(y + h - 1, row_y + 7)), fill=team_color)

                score = str(team.get("score", 0))
                score_w = int(self.font_tall.getlength(score))
                score_x = x + w - score_w - 1
                draw.text((score_x, row_y), score, font=self.font_tall, fill=self.COLOR_MAIN)

                name_x = x + bar_w + 2
                name_max_w = max(1, score_x - name_x - 1)
                name = self._fit_text(str(team.get("abbr", "---")), name_max_w, self.font_tall)
                draw.text((name_x, row_y), name, font=self.font_tall, fill=team_color)

                if game.get("possession") == side and hasattr(self.sports, "_draw_possession_arrow"):
                    arrow_x = name_x + int(self.font_tall.getlength(name)) + 1
                    if arrow_x + 3 < score_x:
                        self.sports._draw_possession_arrow(draw, arrow_x, row_y + 2)

            draw_team_row(away, home, "away", away_y)
            draw_team_row(home, away, "home", home_y)
            return

        away_abbr = str(away.get("abbr", "AWY")).upper()
        home_abbr = str(home.get("abbr", "HME")).upper()
        score = f"{away.get('score', 0)}-{home.get('score', 0)}"
        status = self.sports._status_text(game) if hasattr(self.sports, "_status_text") else ""
        matchup = f"{away_abbr}/{home_abbr}"

        matchup_w = int(self.font_small.getlength(matchup))
        left_w = min(max(10, matchup_w + 4), max(10, w // 3))
        left_w = min(left_w, max(1, w - 6))
        right_w = max(1, w - left_w)

        draw.text(
            (x + max(1, (left_w - matchup_w) // 2), y + max(0, (h - 6) // 2)),
            matchup,
            font=self.font_small,
            fill=self.COLOR_ACCENT,
        )

        scroll_text = f"{score} {status}".strip()
        self._draw_scrolling_text_clipped(
            x + left_w,
            y,
            right_w,
            h,
            scroll_text,
            self.COLOR_MAIN,
            key=f"sports-mini:{matchup}:{score}:{status}",
            speed=12.0,
            always_scroll=False,
            wrap=False,
            align="left",
        )

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
