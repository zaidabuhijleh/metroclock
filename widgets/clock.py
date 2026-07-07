import re
import time
from dataclasses import dataclass
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

import config
import config_manager
import web_server
from core import scroll
from core.widget import Widget
from widgets import icons


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

# Segment-style readability overrides for low-resolution LED panels.
# Keeps the watch-face aesthetic while making ambiguous digits easier to parse.
SEGMENT_MAP_SEGMENT_STYLE = {
    # Add a base foot to "1" so it separates visually from "7".
    "1": {"b", "c", "d"},
}


@dataclass
class ClockTheme:
    bg: tuple[int, int, int]
    primary: tuple[int, int, int]
    accent: tuple[int, int, int]
    accent_2: tuple[int, int, int]
    dim: tuple[int, int, int]


@dataclass(frozen=True)
class ClockPaneBounds:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class ClockFacePane:
    bounds: ClockPaneBounds
    variant: str


@dataclass(frozen=True)
class ClockWidgetPane:
    source: str
    slot: str
    bounds: ClockPaneBounds
    render_mode: str
    scroll_mode_key: str = "primary"

    @property
    def focused(self) -> bool:
        return self.render_mode == "focused"


@dataclass(frozen=True)
class ClockScreenLayout:
    clock_faces: tuple[ClockFacePane, ...]
    widget_panes: tuple[ClockWidgetPane, ...]


class ClockNormalizedGrid:
    """Maps normalized unit coordinates onto pixel bounds."""

    def __init__(self, pixel_width: int, pixel_height: int, unit_width: int, unit_height: int):
        self.pixel_width = max(1, int(pixel_width))
        self.pixel_height = max(1, int(pixel_height))
        self.unit_width = max(1, int(unit_width))
        self.unit_height = max(1, int(unit_height))

    def bounds(self, x_units: float, y_units: float, w_units: float, h_units: float) -> ClockPaneBounds:
        x0 = self._x_boundary(x_units)
        y0 = self._y_boundary(y_units)
        x1 = self._x_boundary(x_units + w_units)
        y1 = self._y_boundary(y_units + h_units)
        x1 = max(x0 + 1, min(self.pixel_width, x1))
        y1 = max(y0 + 1, min(self.pixel_height, y1))
        return ClockPaneBounds(x=x0, y=y0, width=x1 - x0, height=y1 - y0)

    def _x_boundary(self, unit_x: float) -> int:
        ratio = float(unit_x) / float(self.unit_width)
        return max(0, min(self.pixel_width, int(round(ratio * self.pixel_width))))

    def _y_boundary(self, unit_y: float) -> int:
        ratio = float(unit_y) / float(self.unit_height)
        return max(0, min(self.pixel_height, int(round(ratio * self.pixel_height))))


class ClockWidgetPresenter:
    """Object wrapper for a clock-embedded widget source."""

    def __init__(self, source: str, supported_slots, updater, drawer):
        self.source = source
        self._supported_slots = set(supported_slots)
        self._updater = updater
        self._drawer = drawer

    def supports_slot(self, slot: str) -> bool:
        return str(slot or "").strip().lower() in self._supported_slots

    def update(self):
        self._updater()

    def draw(self, draw, pane: ClockWidgetPane):
        self._drawer(draw, pane)


class ClockLayoutPreset:
    """Declarative layout preset object for clock+widget mode."""

    def __init__(self, key: str, label: str, description: str, builder):
        self.key = key
        self.label = label
        self.description = description
        self._builder = builder

    def build(self, clock_widget, grid: ClockNormalizedGrid, sources: tuple[str, str, str]) -> ClockScreenLayout:
        return self._builder(clock_widget, grid, sources)


class ClockWidget(Widget):
    """Standalone clock renderer with shared compact drawing helpers."""

    _SHARED_RENDERED_CLOCK_FACE_CACHE = {}

    COLOR_BG = (0, 0, 0)
    COLOR_MAIN = (232, 238, 255)
    COLOR_ACCENT = (128, 186, 255)
    COLOR_ACCENT_2 = (255, 198, 96)
    COLOR_DIM = (88, 102, 132)
    COLOR_UP = (92, 226, 130)
    COLOR_DOWN = (239, 97, 97)
    COLOR_DIVIDER = (48, 62, 90)
    # Quantized + slightly muted fills reduce perceived temporal-dither shimmer
    # on low-bit-depth matrix backgrounds, especially saturated red.
    COLOR_POMODORO_BG_FOCUS = (184, 56, 56)
    COLOR_POMODORO_BG_BREAK = (48, 136, 72)

    CLOCK_SIZE_OPTIONS = (0.5, 0.75, 1.0)
    FONT_LINE_SHAPES = {
        "matrix": {
            "thickness_ratio": 0.20,
            "draw_unlit": False,
            "colon_size": 1,
            "horizontal": {"mode": "units", "unit_w": 1, "unit_h": 1, "gap": 1, "scale_with_thickness": True},
            "vertical": {"mode": "units", "unit_w": 1, "unit_h": 1, "gap": 1, "scale_with_thickness": True},
        },
        "segment": {
            "thickness_ratio": 0.25,
            "draw_unlit": True,
            "colon_size": 2,
            "horizontal": {"mode": "solid"},
            "vertical": {"mode": "solid"},
        },
    }
    LAYOUT_OPTIONS = {"horizontal", "vertical"}
    WIDGET_SOURCES = {"clock", "metro", "weather", "flight", "sports", "stocks", "pomodoro"}
    SCROLL_MODE_OPTIONS = {"metro", "ticker"}
    MINI_SCROLLABLE_SOURCES = {"metro", "stocks", "sports", "flight"}
    CLOCK_WIDGET_PRESET_OPTIONS = (
        "auto",
        "single_full",
        "horizontal_two",
        "horizontal_two_flipped",
        "vertical_two",
        "horizontal_three",
        "vertical_three",
        # Legacy preset names accepted from older clients/configs.
        "horizontal_single",
        "horizontal_single_top",
        "horizontal_split",
        "vertical_focus",
        "vertical_split_focus",
        "vertical_split_focus_top",
    )
    CLOCK_WIDGET_GRID_WIDTH = 6
    CLOCK_WIDGET_GRID_HEIGHT = 3
    VERTICAL_SIDE_WIDTH_UNITS = 3.0
    WEATHER_MINI_WIDTH_UNITS = 2.0
    LEGACY_PRESET_ALIASES = {
        "horizontal_single": "horizontal_two",
        "horizontal_single_top": "horizontal_two_flipped",
        "horizontal_split": "horizontal_three",
        "vertical_focus": "vertical_two",
        "vertical_split_focus": "vertical_three",
        "vertical_split_focus_top": "vertical_three",
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
        self._metro_mini_hold_key = None
        self._metro_mini_hold_started = 0.0
        self._sports_mini_hold_key = None
        self._sports_mini_hold_started = 0.0
        self._stocks_mini_last_symbol = None
        self._stocks_mini_hold_key = None
        self._stocks_mini_hold_started = 0.0
        self._pomodoro_state_cache = None
        self._last_config_reload = 0.0

        self._clock_face_font_cache = {}
        self._widget_font_cache = {}
        self._widget_font_candidates_cache = None
        self._spleen_font_candidates_cache = None
        self._text_font_fit_cache = {}
        self._scroll_text_render_cache = {}
        self._rendered_clock_face_cache = self._SHARED_RENDERED_CLOCK_FACE_CACHE
        self.font_small = self._load_spleen_size("5x8") or ImageFont.load_default()
        self.font_tall = self._load_spleen_size("6x12") or self.font_small

        self._widget_presenters = self._build_widget_presenters()
        self._layout_presets = self._build_layout_presets()

    # --------------------------------------------------------------- config

    def _font_style(self):
        return "font_spleen"

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

    def _load_spleen_size(self, size_key):
        spec = config.get_spleen_font_size(size_key)
        path = (spec or {}).get("path")
        if not path:
            return None
        try:
            size = int((spec or {}).get("font_size") or (spec or {}).get("height") or self._clock_face_font_size(path))
        except Exception:
            size = self._clock_face_font_size(path)
        cache_key = ("spleen", path, size)
        if cache_key not in self._clock_face_font_cache:
            self._clock_face_font_cache[cache_key] = ImageFont.truetype(path, size)
        return self._clock_face_font_cache[cache_key]

    def _spleen_font_candidates(self):
        if self._spleen_font_candidates_cache is not None:
            return self._spleen_font_candidates_cache

        fonts = []
        for size in config.get_spleen_font_sizes():
            font = self._load_spleen_size(size.get("key"))
            if font is None:
                continue
            fonts.append((int(size.get("height") or self._clock_face_font_size(size.get("path"))), font, size))
        fonts.sort(key=lambda item: item[0])
        if not fonts:
            fonts.append((6, self.font_small, {"key": "fallback", "height": 6}))
        self._spleen_font_candidates_cache = tuple(fonts)
        return fonts

    def _font_text_height(self, draw, text, font):
        _left, _top, _width, height = self._font_text_metrics(draw, text or "0", font)
        return max(1, height)

    def _load_widget_font(self, key, path, size):
        cache_key = (key, path, int(size))
        if cache_key not in self._widget_font_cache:
            self._widget_font_cache[cache_key] = ImageFont.truetype(path, int(size))
        return self._widget_font_cache[cache_key]

    def _widget_font_candidates(self):
        if self._widget_font_candidates_cache is not None:
            return self._widget_font_candidates_cache

        specs = (
            ("4x6", config.FONT_PATH_SMALL, config.FONT_SIZE_SMALL),
            ("spleen-5x8", "assets/fonts/spleen/5x8.bdf", 8),
            ("spleen-6x12", "assets/fonts/spleen/6x12.bdf", 12),
            ("spleen-8x16", "assets/fonts/spleen/8x16.bdf", 16),
            ("spleen-12x24", "assets/fonts/spleen/12x24.bdf", 24),
        )
        fonts = []
        for key, path, size in specs:
            try:
                fonts.append((int(size), self._load_widget_font(key, path, size), {"key": key, "height": int(size)}))
            except Exception:
                continue
        if not fonts:
            fonts.append((6, ImageFont.load_default(), {"key": "fallback", "height": 6}))
        self._widget_font_candidates_cache = tuple(fonts)
        return self._widget_font_candidates_cache

    def _font_for_box(self, draw, text, max_width, max_height, *, prefer_width_fit=True):
        text = str(text or "")
        max_width = max(1, int(max_width))
        max_height = max(1, int(max_height))
        cache_key = (text, max_width, max_height, bool(prefer_width_fit))
        cached = self._text_font_fit_cache.get(cache_key)
        if cached is not None:
            return cached

        candidates = self._widget_font_candidates()
        selected = candidates[0][1]
        for _height, font, _size in candidates:
            left, top, width, height = self._font_text_metrics(draw, text or "0", font)
            if height <= max_height and (not prefer_width_fit or width <= max_width):
                selected = font
        self._text_font_fit_cache[cache_key] = selected
        return selected

    def _draw_text_box(self, draw, box, text, fill, *, align="center", valign="center", ellipsis="..."):
        x, y, w, h = box
        if w <= 0 or h <= 0:
            return
        font = self._font_for_box(draw, text, max(1, w - 2), max(1, h), prefer_width_fit=True)
        fit = self._fit_text(text, max(1, w - 2), font, ellipsis=ellipsis)
        left, top, text_w, text_h = self._font_text_metrics(draw, fit, font)
        if align == "left":
            tx = x + 1 - left
        elif align == "right":
            tx = x + max(1, w - text_w - 1) - left
        else:
            tx = x + max(0, (w - text_w) // 2) - left
        if valign == "top":
            ty = y - top
        elif valign == "bottom":
            ty = y + max(0, h - text_h) - top
        else:
            ty = y + max(0, (h - text_h) // 2) - top
        draw.text((tx, ty), fit, font=font, fill=fill)
        return font

    def _layout(self):
        layout = str(getattr(config, "CLOCK_WIDGET_LAYOUT", "horizontal") or "horizontal").strip().lower()
        return layout if layout in self.LAYOUT_OPTIONS else "horizontal"

    def _widget_source(self):
        source = str(getattr(config, "CLOCK_WIDGET_SOURCE", "weather") or "weather").strip().lower()
        return source if source in self.WIDGET_SOURCES else "weather"

    def _widget_source_secondary(self):
        source = str(getattr(config, "CLOCK_WIDGET_SOURCE_SECONDARY", "stocks") or "stocks").strip().lower()
        return source if source in self.WIDGET_SOURCES else "stocks"

    def _widget_slot_source(self, slot_key: str, fallback: str):
        config_key = f"CLOCK_WIDGET_SLOT_{slot_key.upper()}_SOURCE"
        source = str(getattr(config, config_key, fallback) or fallback).strip().lower()
        return source if source in self.WIDGET_SOURCES else fallback

    def _widget_slot_sources(self):
        return (
            self._widget_slot_source("a", "clock"),
            self._widget_slot_source("b", self._widget_source()),
            self._widget_slot_source("c", self._widget_source_secondary()),
        )

    def _widget_count(self):
        try:
            count = int(getattr(config, "CLOCK_WIDGET_COUNT", 1))
        except Exception:
            count = 1
        return 2 if count >= 2 else 1

    def _widget_preset(self):
        preset = str(getattr(config, "CLOCK_WIDGET_PRESET", "auto") or "auto").strip().lower()
        return preset if preset in self.CLOCK_WIDGET_PRESET_OPTIONS else "auto"

    def _infer_widget_preset_from_legacy(self):
        layout = self._layout()
        widget_count = self._widget_count()
        if layout == "vertical":
            return "vertical_three" if widget_count >= 2 else "vertical_two"
        return "horizontal_three" if widget_count >= 2 else "horizontal_two"

    def _active_widget_preset(self):
        requested = self._widget_preset()
        if requested == "auto":
            return self._infer_widget_preset_from_legacy()
        return self.LEGACY_PRESET_ALIASES.get(requested, requested)

    def _use_24h(self):
        return bool(getattr(config, "CLOCK_USE_24H", False))

    def _normalize_scroll_mode(self, mode, fallback="metro"):
        value = str(mode or fallback).strip().lower()
        return value if value in self.SCROLL_MODE_OPTIONS else fallback

    def _widget_scroll_mode_for_key(self, key="primary"):
        legacy = getattr(config, "CLOCK_WIDGET_SCROLL_MODE", "metro")
        primary = self._normalize_scroll_mode(
            getattr(config, "CLOCK_WIDGET_SCROLL_MODE_PRIMARY", legacy),
            fallback=self._normalize_scroll_mode(legacy, fallback="metro"),
        )
        if str(key or "primary").strip().lower() == "secondary":
            secondary = getattr(config, "CLOCK_WIDGET_SCROLL_MODE_SECONDARY", primary)
            return self._normalize_scroll_mode(secondary, fallback=primary)
        if str(key or "primary").strip().lower() == "tertiary":
            tertiary = getattr(config, "CLOCK_WIDGET_SCROLL_MODE_TERTIARY", primary)
            return self._normalize_scroll_mode(tertiary, fallback=primary)
        return primary

    def _widget_scroll_mode_for_pane(self, pane: ClockWidgetPane):
        source = str(getattr(pane, "source", "") or "").strip().lower()
        if source not in self.MINI_SCROLLABLE_SOURCES:
            return "metro"
        return self._widget_scroll_mode_for_key(getattr(pane, "scroll_mode_key", "primary"))

    def _normalized_clock_grid(self):
        return ClockNormalizedGrid(
            pixel_width=self.width,
            pixel_height=self.height,
            unit_width=self.CLOCK_WIDGET_GRID_WIDTH,
            unit_height=self.CLOCK_WIDGET_GRID_HEIGHT,
        )

    def _bottom_split_units(self, source_a: str, source_b: str):
        total = float(self.CLOCK_WIDGET_GRID_WIDTH)
        weather_units = max(1.0, min(total - 1.0, float(self.WEATHER_MINI_WIDTH_UNITS)))
        src_a = str(source_a or "").strip().lower()
        src_b = str(source_b or "").strip().lower()

        if src_a == "weather" and src_b != "weather":
            return weather_units, total - weather_units
        if src_b == "weather" and src_a != "weather":
            return total - weather_units, weather_units
        # Equal split when neither or both sides are weather.
        return total / 2.0, total / 2.0

    def _mini_scroll_args(self, scroll_mode="metro", *, default_align="left"):
        mode = self._normalize_scroll_mode(scroll_mode, fallback="metro")
        if mode == "ticker":
            return {
                "always_scroll": True,
                "wrap": True,
                "restart_on_end": True,
                "align": default_align,
            }
        return {
            "always_scroll": False,
            "wrap": False,
            "restart_on_end": False,
            "align": default_align,
        }

    def _build_widget_presenters(self):
        return {
            "clock": ClockWidgetPresenter(
                source="clock",
                supported_slots={"full", "horizontal", "vertical"},
                updater=lambda: None,
                drawer=self._draw_clock_pane,
            ),
            "metro": ClockWidgetPresenter(
                source="metro",
                supported_slots={"full", "horizontal"},
                updater=self.metro.update,
                drawer=self._draw_metro_pane,
            ),
            "weather": ClockWidgetPresenter(
                source="weather",
                supported_slots={"full", "horizontal", "vertical"},
                updater=self.weather.update,
                drawer=self._draw_weather_pane,
            ),
            "flight": ClockWidgetPresenter(
                source="flight",
                supported_slots={"full", "horizontal"},
                updater=self.flight.update,
                drawer=self._draw_flight_pane,
            ),
            "sports": ClockWidgetPresenter(
                source="sports",
                supported_slots={"full", "horizontal", "vertical"},
                updater=self.sports.update,
                drawer=self._draw_sports_pane,
            ),
            "stocks": ClockWidgetPresenter(
                source="stocks",
                supported_slots={"full", "horizontal", "vertical"},
                updater=self._update_stocks_for_clock,
                drawer=self._draw_stocks_pane,
            ),
            "pomodoro": ClockWidgetPresenter(
                source="pomodoro",
                supported_slots={"full", "horizontal", "vertical"},
                updater=self._update_pomodoro_for_clock,
                drawer=self._draw_pomodoro_pane,
            ),
        }

    def _draw_clock_pane(self, draw, pane: ClockWidgetPane):
        variant = "full"
        if pane.slot == "horizontal":
            variant = "horizontal"
        elif pane.slot == "vertical":
            variant = "vertical_focus"
        face = self._render_clock_face(
            pane.bounds.width,
            pane.bounds.height,
            variant,
            self._clock_theme(),
        )
        self.canvas.paste(face, (pane.bounds.x, pane.bounds.y))

    def _build_layout_presets(self):
        return {
            "single_full": ClockLayoutPreset(
                key="single_full",
                label="One Full Slot",
                description="One widget source fills the whole display.",
                builder=ClockWidget._layout_preset_single_full,
            ),
            "horizontal_two": ClockLayoutPreset(
                key="horizontal_two",
                label="Top Focus + Bottom Strip",
                description="Large top slot with a short bottom slot.",
                builder=ClockWidget._layout_preset_horizontal_two,
            ),
            "horizontal_two_flipped": ClockLayoutPreset(
                key="horizontal_two_flipped",
                label="Top Strip + Bottom Focus",
                description="Short top slot with a large bottom slot.",
                builder=ClockWidget._layout_preset_horizontal_two_flipped,
            ),
            "vertical_two": ClockLayoutPreset(
                key="vertical_two",
                label="Left + Right Split",
                description="Two side-by-side focus slots.",
                builder=ClockWidget._layout_preset_vertical_two,
            ),
            "horizontal_three": ClockLayoutPreset(
                key="horizontal_three",
                label="Top Focus + Two Bottom Slots",
                description="Large top slot with two compact bottom slots.",
                builder=ClockWidget._layout_preset_horizontal_three,
            ),
            "vertical_three": ClockLayoutPreset(
                key="vertical_three",
                label="Left Focus + Two Right Slots",
                description="Large left slot with two stacked right slots.",
                builder=ClockWidget._layout_preset_vertical_three,
            ),
        }

    def _draw_metro_pane(self, draw, pane: ClockWidgetPane):
        self._draw_widget_metro(
            draw,
            pane.bounds.x,
            pane.bounds.y,
            pane.bounds.width,
            pane.bounds.height,
            scroll_mode=self._widget_scroll_mode_for_pane(pane),
        )

    def _draw_weather_pane(self, draw, pane: ClockWidgetPane):
        self._draw_widget_weather(
            draw,
            pane.bounds.x,
            pane.bounds.y,
            pane.bounds.width,
            pane.bounds.height,
            focused=pane.focused,
        )

    def _draw_flight_pane(self, draw, pane: ClockWidgetPane):
        self._draw_widget_flight(
            draw,
            pane.bounds.x,
            pane.bounds.y,
            pane.bounds.width,
            pane.bounds.height,
            scroll_mode=self._widget_scroll_mode_for_pane(pane),
        )

    def _draw_sports_pane(self, draw, pane: ClockWidgetPane):
        self._draw_widget_sports(
            draw,
            pane.bounds.x,
            pane.bounds.y,
            pane.bounds.width,
            pane.bounds.height,
            focused=pane.focused,
            scroll_mode=self._widget_scroll_mode_for_pane(pane),
        )

    def _draw_stocks_pane(self, draw, pane: ClockWidgetPane):
        self._draw_widget_stocks(
            draw,
            pane.bounds.x,
            pane.bounds.y,
            pane.bounds.width,
            pane.bounds.height,
            focused=pane.focused,
            scroll_mode=self._widget_scroll_mode_for_pane(pane),
        )

    def _draw_pomodoro_pane(self, draw, pane: ClockWidgetPane):
        self._draw_widget_pomodoro(
            draw,
            pane.bounds.x,
            pane.bounds.y,
            pane.bounds.width,
            pane.bounds.height,
            focused=pane.focused,
        )

    def _update_stocks_for_clock(self):
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

    def _update_pomodoro_for_clock(self):
        try:
            self._pomodoro_state_cache = web_server.get_pomodoro_state()
        except Exception:
            # Keep rendering with the last known state when the API momentarily fails.
            pass

    # --------------------------------------------------------------- state

    def update(self):
        now = time.time()
        if now - self._last_config_reload >= 1.0:
            config_manager.reload_config()
            self._last_config_reload = now

    # --------------------------------------------------------------- draw

    def draw(self):
        theme = self._clock_theme()
        self.canvas = Image.new("RGB", (self.width, self.height), theme.bg)
        face = self._render_clock_face(self.width, self.height, "full", theme)
        self.canvas.paste(face, (0, 0))
        return self.canvas

    def _rotate_embedded_indices(self):
        now = time.time()
        if now - self._last_widget_rotate < self._widget_rotate_seconds:
            return

        symbols = self._stock_symbols()
        if symbols:
            self._stock_idx = (self._stock_idx + 1) % len(symbols)

        self._last_widget_rotate = now

    def _build_clock_screen_layout(self) -> ClockScreenLayout:
        grid = self._normalized_clock_grid()
        preset_key = self._active_widget_preset()
        preset = self._layout_presets.get(preset_key) or self._layout_presets["horizontal_two"]
        return preset.build(self, grid, self._widget_slot_sources())

    def _pane(self, source_req: str, slot: str, bounds: ClockPaneBounds, render_mode: str, scroll_key: str) -> ClockWidgetPane:
        return ClockWidgetPane(
            source=self._resolve_supported_source(source_req, slot),
            slot=slot,
            bounds=bounds,
            render_mode=render_mode,
            scroll_mode_key=scroll_key,
        )

    def _layout_preset_single_full(self, grid: ClockNormalizedGrid, sources: tuple[str, str, str]) -> ClockScreenLayout:
        widget_panes = (
            self._pane(
                sources[0],
                "full",
                grid.bounds(0.0, 0.0, float(self.CLOCK_WIDGET_GRID_WIDTH), float(self.CLOCK_WIDGET_GRID_HEIGHT)),
                "focused",
                "primary",
            ),
        )
        return ClockScreenLayout(clock_faces=(), widget_panes=widget_panes)

    def _layout_preset_horizontal_two(self, grid: ClockNormalizedGrid, sources: tuple[str, str, str]) -> ClockScreenLayout:
        widget_panes = (
            self._pane(
                sources[0],
                "horizontal",
                grid.bounds(0.0, 0.0, float(self.CLOCK_WIDGET_GRID_WIDTH), 2.0),
                "focused",
                "primary",
            ),
            ClockWidgetPane(
                source=self._resolve_supported_source(sources[1], "horizontal"),
                slot="horizontal",
                bounds=grid.bounds(0.0, 2.0, float(self.CLOCK_WIDGET_GRID_WIDTH), 1.0),
                render_mode="compact",
                scroll_mode_key="secondary",
            ),
        )
        return ClockScreenLayout(clock_faces=(), widget_panes=widget_panes)

    def _layout_preset_horizontal_two_flipped(self, grid: ClockNormalizedGrid, sources: tuple[str, str, str]) -> ClockScreenLayout:
        widget_panes = (
            self._pane(
                sources[0],
                "horizontal",
                grid.bounds(0.0, 0.0, float(self.CLOCK_WIDGET_GRID_WIDTH), 1.0),
                "compact",
                "primary",
            ),
            self._pane(
                sources[1],
                "horizontal",
                grid.bounds(0.0, 1.0, float(self.CLOCK_WIDGET_GRID_WIDTH), 2.0),
                "focused",
                "secondary",
            ),
        )
        return ClockScreenLayout(clock_faces=(), widget_panes=widget_panes)

    def _layout_preset_vertical_two(self, grid: ClockNormalizedGrid, sources: tuple[str, str, str]) -> ClockScreenLayout:
        left_units = float(self.CLOCK_WIDGET_GRID_WIDTH) / 2.0
        right_units = float(self.CLOCK_WIDGET_GRID_WIDTH) - left_units
        widget_panes = (
            self._pane(
                sources[0],
                "vertical",
                grid.bounds(0.0, 0.0, left_units, float(self.CLOCK_WIDGET_GRID_HEIGHT)),
                "focused",
                "primary",
            ),
            self._pane(
                sources[1],
                "vertical",
                grid.bounds(left_units, 0.0, right_units, float(self.CLOCK_WIDGET_GRID_HEIGHT)),
                "focused",
                "secondary",
            ),
        )
        return ClockScreenLayout(clock_faces=(), widget_panes=widget_panes)

    def _layout_preset_horizontal_three(self, grid: ClockNormalizedGrid, sources: tuple[str, str, str]) -> ClockScreenLayout:
        source_b = self._resolve_supported_source(sources[1], "horizontal")
        source_c = self._resolve_supported_source(sources[2], "horizontal")
        left_units, right_units = self._bottom_split_units(source_b, source_c)
        widget_panes = (
            self._pane(
                sources[0],
                "horizontal",
                grid.bounds(0.0, 0.0, float(self.CLOCK_WIDGET_GRID_WIDTH), 2.0),
                "focused",
                "primary",
            ),
            ClockWidgetPane(
                source=source_b,
                slot="horizontal",
                bounds=grid.bounds(0.0, 2.0, left_units, 1.0),
                render_mode="compact",
                scroll_mode_key="secondary",
            ),
            ClockWidgetPane(
                source=source_c,
                slot="horizontal",
                bounds=grid.bounds(left_units, 2.0, right_units, 1.0),
                render_mode="compact",
                scroll_mode_key="tertiary",
            ),
        )
        return ClockScreenLayout(clock_faces=(), widget_panes=widget_panes)

    def _layout_preset_vertical_three(self, grid: ClockNormalizedGrid, sources: tuple[str, str, str]) -> ClockScreenLayout:
        left_units = max(1.0, min(float(self.CLOCK_WIDGET_GRID_WIDTH - 1), float(self.VERTICAL_SIDE_WIDTH_UNITS)))
        right_units = float(self.CLOCK_WIDGET_GRID_WIDTH) - left_units
        widget_panes = (
            self._pane(
                sources[0],
                "vertical",
                grid.bounds(0.0, 0.0, left_units, float(self.CLOCK_WIDGET_GRID_HEIGHT)),
                "focused",
                "primary",
            ),
            self._pane(
                sources[1],
                "horizontal",
                grid.bounds(left_units, 0.0, right_units, 1.5),
                "compact",
                "secondary",
            ),
            self._pane(
                sources[2],
                "horizontal",
                grid.bounds(left_units, 1.5, right_units, 1.5),
                "compact",
                "tertiary",
            ),
        )
        return ClockScreenLayout(clock_faces=(), widget_panes=widget_panes)

    # --------------------------------------------------------------- clock faces

    def _render_clock_face(self, w, h, variant, theme):
        cache_key = self._clock_face_render_cache_key(w, h, variant, theme)
        cached = self._rendered_clock_face_cache.get(cache_key)
        if cached is not None:
            return cached.copy()

        img = Image.new("RGB", (max(1, w), max(1, h)), theme.bg)
        d = ImageDraw.Draw(img)
        style = self._font_style()

        try:
            self._draw_face_font(d, w, h, variant, theme, style)
        except Exception:
            # Keep clock mode alive even if one face errors in an edge case.
            try:
                d.text((1, 1), self._time_text(False), font=self.font_tall, fill=theme.primary)
            except Exception:
                d.text((1, 1), self._time_text(False), font=self.font_small, fill=theme.primary)

        if len(self._rendered_clock_face_cache) >= 32:
            self._rendered_clock_face_cache.pop(next(iter(self._rendered_clock_face_cache)), None)
        self._rendered_clock_face_cache[cache_key] = img.copy()
        return img

    def _clock_face_render_cache_key(self, w, h, variant, theme):
        now, hour, ampm = self._time_parts()
        time_text = f"{hour:02d}:{now.minute:02d}"
        return (
            int(w),
            int(h),
            str(variant),
            time_text,
            now.strftime("%Y-%m-%d"),
            now.strftime("%a %b %d").upper(),
            ampm,
            self._use_24h(),
            self._show_date(),
            self._show_ampm(),
            str(getattr(config, "CLOCK_OVERLAY_ORDER", "ampm_date") or "ampm_date"),
            self._effective_clock_size(),
            self._clock_face_size_key(),
            theme.bg,
            theme.primary,
            theme.accent,
            theme.accent_2,
            theme.dim,
            self._parse_color_override(getattr(config, "CLOCK_DATE_COLOR", "")),
            self._parse_color_override(getattr(config, "CLOCK_AMPM_COLOR", "")),
        )

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

    def _font_line_profile(self, style):
        fallback = self.FONT_LINE_SHAPES["segment"]
        profile = self.FONT_LINE_SHAPES.get(style, fallback)

        try:
            thickness_ratio = float(profile.get("thickness_ratio", fallback["thickness_ratio"]))
        except Exception:
            thickness_ratio = float(fallback["thickness_ratio"])
        thickness_ratio = max(0.08, min(0.45, thickness_ratio))

        try:
            colon_size = int(profile.get("colon_size", fallback["colon_size"]))
        except Exception:
            colon_size = int(fallback["colon_size"])
        colon_size = max(1, colon_size)

        horizontal = dict(profile.get("horizontal") or fallback.get("horizontal") or {"mode": "solid"})
        vertical = dict(profile.get("vertical") or fallback.get("vertical") or {"mode": "solid"})

        return {
            "thickness_ratio": thickness_ratio,
            "draw_unlit": bool(profile.get("draw_unlit", fallback.get("draw_unlit", True))),
            "colon_size": colon_size,
            "horizontal": horizontal,
            "vertical": vertical,
        }

    def _clock_layout_metrics(self, w, h, variant):
        style = self._font_style()
        profile = self._font_line_profile(style)
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
        colon_w = profile["colon_size"]
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
        def draw_overlay(slot, content):
            if content == "date":
                if not self._show_date():
                    return
                text = date_text
                color = self._parse_color_override(getattr(config, "CLOCK_DATE_COLOR", "")) or theme.accent
                y_offset = -1 if slot == "top" else 1
            elif content == "ampm":
                if not (self._show_ampm() and ampm and not self._use_24h()):
                    return
                text = ampm
                color = self._parse_color_override(getattr(config, "CLOCK_AMPM_COLOR", "")) or theme.accent_2
                y_offset = -1 if slot == "top" else 1
            else:
                return

            band_key = "top_band" if slot == "top" else "bottom_band"
            band_h = metrics.get(band_key, 0)
            if band_h <= 0:
                return
            font = self._font_for_box(draw, text, max(1, w - 2), max(1, band_h), prefer_width_fit=True)
            left, top, text_w, text_h = self._font_text_metrics(draw, text, font)
            if slot == "top":
                y = max(0, (band_h - text_h) // 2) - top + y_offset
            else:
                y = h - band_h + max(0, (band_h - text_h) // 2) - top + y_offset
            x = max(0, (w - text_w) // 2) - left
            draw.text((x, y), text, font=font, fill=color)

        order = str(getattr(config, "CLOCK_OVERLAY_ORDER", "ampm_date") or "ampm_date").strip().lower()
        slots = {
            "top": "date" if order == "date_ampm" else "ampm",
            "bottom": "ampm" if order == "date_ampm" else "date",
        }
        draw_overlay("top", slots["top"])
        draw_overlay("bottom", slots["bottom"])

    def _clock_face_size_key(self):
        size = self._effective_clock_size()
        if size >= 1.0:
            return "12x24"
        if size >= 0.75:
            return "8x16"
        return "5x8"

    def _clock_face_font_spec(self):
        size_key = self._clock_face_size_key()
        spec = config.get_spleen_font_size(size_key)
        return {
            "path": (spec or {}).get("path"),
            "scale": max(1, int((spec or {}).get("scale") or 1)),
            "font_size": (spec or {}).get("font_size"),
        }

    def _clock_face_font_size(self, path):
        label = str(path or "")
        match = re.search(r"(\d+)x(\d+)", label, re.IGNORECASE)
        if match:
            return max(1, int(match.group(2)))
        return 10

    def _load_clock_face_font(self):
        spec = self._clock_face_font_spec()
        path = spec["path"]
        if not path:
            return None
        try:
            size = int(spec.get("font_size") or self._clock_face_font_size(path))
        except Exception:
            size = self._clock_face_font_size(path)
        cache_key = (path, size)
        if cache_key not in self._clock_face_font_cache:
            self._clock_face_font_cache[cache_key] = ImageFont.truetype(path, size)
        return self._clock_face_font_cache[cache_key]

    def _font_text_metrics(self, draw, text, font):
        if hasattr(draw, "textbbox"):
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            return left, top, right - left, bottom - top
        left, top, right, bottom = font.getbbox(text)
        return left, top, right - left, bottom - top

    def _draw_face_font(self, draw, w, h, variant, theme, style):
        now, hour, ampm = self._time_parts()
        time_text = f"{hour:02d}:{now.minute:02d}"
        date_text = now.strftime("%a %b %d").upper()
        metrics = {
            "top_band": self._overlay_band_height(h, variant, self._show_ampm() and ampm and not self._use_24h()),
            "bottom_band": self._overlay_band_height(h, variant, self._show_date()),
        }
        if variant == "full":
            font = self._load_clock_face_font()
        else:
            available_h = max(1, h - metrics["top_band"] - metrics["bottom_band"])
            font = self._font_for_box(draw, time_text, max(1, w - 2), available_h, prefer_width_fit=True)
        if font is None:
            draw.text((1, 1), self._time_text(False), font=self.font_tall, fill=theme.primary)
            return

        clock_top = metrics["top_band"]
        clock_bottom = max(clock_top + 1, h - metrics["bottom_band"])
        text_left, text_top, text_w, text_h = self._font_text_metrics(draw, time_text, font)
        scale = self._clock_face_font_spec()["scale"]
        if scale > 1:
            text_img = Image.new("RGB", (max(1, text_w), max(1, text_h)), theme.bg)
            text_draw = ImageDraw.Draw(text_img)
            text_draw.text((-text_left, -text_top), time_text, font=font, fill=theme.primary)
            text_img = text_img.resize((text_img.width * scale, text_img.height * scale), Image.Resampling.NEAREST)
            x = max(0, (w - text_img.width) // 2)
            y = clock_top + max(0, (clock_bottom - clock_top - text_img.height) // 2)
            draw.bitmap((x, y), text_img.convert("1"), fill=theme.primary)
        else:
            x = max(0, (w - text_w) // 2) - text_left
            y = clock_top + max(0, (clock_bottom - clock_top - text_h) // 2) - text_top
            draw.text((x, y), time_text, font=font, fill=theme.primary)

        self._draw_clock_overlays(
            draw,
            w,
            h,
            variant,
            ampm,
            theme,
            date_text,
            metrics,
        )

    def _segment_rects_for_digit(self, x, y, dw, dh, thickness, digit):
        thickness = max(1, min(thickness, max(1, min(dw // 3, dh // 4))))
        half = dh // 2
        mid_top = max(y + thickness, y + half - thickness // 2)
        mid_bottom = min(y + dh - thickness - 1, mid_top + thickness - 1)
        upper_end = max(y + thickness, mid_top - 1)
        lower_start = min(y + dh - thickness - 1, mid_bottom + 1)
        rects = {
            "a": (x + thickness, y, x + dw - thickness - 1, y + thickness - 1),
            "g": (x + thickness, mid_top, x + dw - thickness - 1, mid_bottom),
            "d": (x + thickness, y + dh - thickness, x + dw - thickness - 1, y + dh - 1),
        }
        if upper_end >= y + thickness:
            rects["f"] = (x, y + thickness, x + thickness - 1, upper_end)
            rects["b"] = (x + dw - thickness, y + thickness, x + dw - 1, upper_end)
        if y + dh - thickness - 1 >= lower_start:
            rects["e"] = (x, lower_start, x + thickness - 1, y + dh - thickness - 1)
            c_end = y + dh - thickness - 1
            # Make "4" feel slightly taller by extending the lower-right stem
            # by one size unit (thickness scales with font size preset).
            if str(digit) == "4":
                c_end = min(y + dh - 1, c_end + thickness)
            rects["c"] = (x + dw - thickness, lower_start, x + dw - 1, c_end)
        return rects, thickness

    def _draw_line_shape(self, draw, rect, color, shape, thickness):
        x1, y1, x2, y2 = rect
        if x2 < x1 or y2 < y1:
            return
        mode = str((shape or {}).get("mode", "solid")).strip().lower()
        if mode != "units":
            draw.rectangle(rect, fill=color)
            return

        w = x2 - x1 + 1
        h = y2 - y1 + 1
        try:
            unit_w = int((shape or {}).get("unit_w", 1))
        except Exception:
            unit_w = 1
        try:
            unit_h = int((shape or {}).get("unit_h", 1))
        except Exception:
            unit_h = 1
        try:
            gap = int((shape or {}).get("gap", 1))
        except Exception:
            gap = 1

        if bool((shape or {}).get("scale_with_thickness", False)):
            scale = max(1, thickness)
            unit_w *= scale
            unit_h *= scale

        unit_w = max(1, min(unit_w, w))
        unit_h = max(1, min(unit_h, h))
        gap = max(0, gap)
        step_x = max(1, unit_w + gap)
        step_y = max(1, unit_h + gap)

        if w >= h:
            y_start = y1 + max(0, (h - unit_h) // 2)
            positions = []
            pos = x1
            end_pos = x2 - unit_w + 1
            while pos <= end_pos:
                positions.append(pos)
                pos += step_x
            if not positions:
                positions = [x1]
            elif positions[-1] < end_pos:
                positions.append(end_pos)
            for px in positions:
                draw.rectangle((px, y_start, min(x2, px + unit_w - 1), min(y2, y_start + unit_h - 1)), fill=color)
            return

        x_start = x1 + max(0, (w - unit_w) // 2)
        positions = []
        pos = y1
        end_pos = y2 - unit_h + 1
        while pos <= end_pos:
            positions.append(pos)
            pos += step_y
        if not positions:
            positions = [y1]
        elif positions[-1] < end_pos:
            positions.append(end_pos)
        for py in positions:
            draw.rectangle((x_start, py, min(x2, x_start + unit_w - 1), min(y2, py + unit_h - 1)), fill=color)

    def _draw_segment_digit(self, draw, x, y, dw, dh, digit, on, off, style):
        profile = self._font_line_profile(style)
        base_thickness = max(1, int(round(min(dw, dh) * profile["thickness_ratio"])))
        rects, thickness = self._segment_rects_for_digit(x, y, dw, dh, base_thickness, digit)
        segs = SEGMENT_MAP.get(digit, set())
        if style == "segment":
            segs = SEGMENT_MAP_SEGMENT_STYLE.get(digit, segs)
        draw_unlit = profile["draw_unlit"]

        for seg, rect in rects.items():
            lit = seg in segs
            if not lit and not draw_unlit:
                continue
            color = on if lit else off
            rect_w = rect[2] - rect[0] + 1
            rect_h = rect[3] - rect[1] + 1
            line_shape = profile["horizontal"] if rect_w >= rect_h else profile["vertical"]
            self._draw_line_shape(draw, rect, color, line_shape, thickness)

    def _draw_colon(self, draw, x, y, digit_h, theme, style):
        blink_on = (time.time() % 1.0) > 0.25
        if not blink_on:
            return
        profile = self._font_line_profile(style)
        dot = max(1, profile["colon_size"])
        draw.rectangle((x, y + digit_h // 3, x + dot - 1, y + digit_h // 3 + dot - 1), fill=theme.accent_2)
        draw.rectangle((x, y + (digit_h * 2) // 3, x + dot - 1, y + (digit_h * 2) // 3 + dot - 1), fill=theme.accent_2)

    def _draw_face_digital_common(self, draw, w, h, variant, theme, style):
        now, hour, ampm = self._time_parts()
        digits = f"{hour:02d}{now.minute:02d}"
        metrics = self._clock_layout_metrics(w, h, variant)
        # Reduce inactive segment glow in segment mode to improve contrast.
        off_divisor = 6 if style == "segment" else 4
        off = tuple(max(0, c // off_divisor) for c in theme.dim)
        date_text = now.strftime("%a %b %d").upper() if style == "matrix" else now.strftime("%a %m/%d").upper()

        for digit_index, ch in enumerate(digits):
            x = metrics["x0"] + digit_index * (metrics["digit_w"] + metrics["spacing"])
            if digit_index >= 2:
                x += metrics["colon_w"] + metrics["spacing"]
            self._draw_segment_digit(draw, x, metrics["y0"], metrics["digit_w"], metrics["digit_h"], ch, theme.primary, off, style)

        colon_left = metrics["x0"] + 2 * (metrics["digit_w"] + metrics["spacing"])
        cx = colon_left + max(0, (metrics["colon_w"] - 1) // 2)
        self._draw_colon(draw, cx, metrics["y0"], metrics["digit_h"], theme, style)

        self._draw_clock_overlays(
            draw,
            w,
            h,
            variant,
            ampm,
            theme,
            date_text,
            metrics,
        )

    def _draw_face_digital_matrix(self, draw, w, h, variant, theme):
        self._draw_face_digital_common(draw, w, h, variant, theme, "matrix")

    def _draw_face_digital_segment(self, draw, w, h, variant, theme):
        self._draw_face_digital_common(draw, w, h, variant, theme, "segment")

    def draw_segment_test(self):
        """Render readability test: cycle 01..24 and display as NN:NN."""
        theme = self._clock_theme()
        self.canvas = Image.new("RGB", (self.width, self.height), theme.bg)
        draw = ImageDraw.Draw(self.canvas)

        test_value = (int(time.time()) % 24) + 1
        digits = f"{test_value:02d}{test_value:02d}"
        metrics = self._clock_layout_metrics(self.width, self.height, "full")
        off = tuple(max(0, c // 6) for c in theme.dim)

        for digit_index, ch in enumerate(digits):
            x = metrics["x0"] + digit_index * (metrics["digit_w"] + metrics["spacing"])
            if digit_index >= 2:
                x += metrics["colon_w"] + metrics["spacing"]
            self._draw_segment_digit(
                draw,
                x,
                metrics["y0"],
                metrics["digit_w"],
                metrics["digit_h"],
                ch,
                theme.primary,
                off,
                "segment",
            )

        colon_left = metrics["x0"] + 2 * (metrics["digit_w"] + metrics["spacing"])
        cx = colon_left + max(0, (metrics["colon_w"] - 1) // 2)
        self._draw_colon(draw, cx, metrics["y0"], metrics["digit_h"], theme, "segment")

        title = "SEG TEST"
        progress = f"{test_value:02d}/24"
        tw = int(self.font_small.getlength(title))
        pw = int(self.font_small.getlength(progress))
        draw.text((max(0, (self.width - tw) // 2), 0), title, font=self.font_small, fill=theme.accent_2)
        draw.text((max(0, (self.width - pw) // 2), max(0, self.height - 7)), progress, font=self.font_small, fill=theme.accent)

        return self.canvas

    # --------------------------------------------------------------- widget region

    def _resolve_supported_source(self, requested, slot):
        source = str(requested or "").strip().lower()
        if source not in self.WIDGET_SOURCES:
            source = "weather"
        presenter = self._widget_presenters.get(source)
        slot_key = str(slot or "").strip().lower()
        if presenter is not None and presenter.supports_slot(slot_key):
            return source

        fallback_order = {
            "full": ("clock", "weather", "pomodoro", "stocks", "sports"),
            "vertical": ("clock", "weather", "pomodoro", "stocks", "sports"),
            "horizontal": ("clock", "weather", "pomodoro", "metro", "flight", "sports", "stocks"),
        }
        for candidate in fallback_order.get(slot_key, ("weather",)):
            candidate_presenter = self._widget_presenters.get(candidate)
            if candidate_presenter is None:
                continue
            if candidate_presenter.supports_slot(slot_key):
                return candidate
        return "weather"

    def _draw_widget_region(self, draw, x, y, w, h, source, focused=False):
        pane = ClockWidgetPane(
            source=str(source or "").strip().lower(),
            slot="vertical" if focused else "horizontal",
            bounds=ClockPaneBounds(x, y, w, h),
            render_mode="focused" if focused else "compact",
            scroll_mode_key="primary",
        )
        self._draw_widget_pane(draw, pane)

    def _draw_widget_pane(self, draw, pane: ClockWidgetPane):
        if pane.bounds.width <= 0 or pane.bounds.height <= 0:
            return

        presenter = self._widget_presenters.get(pane.source)
        if presenter is None:
            self._draw_text_box(
                draw,
                (pane.bounds.x, pane.bounds.y, pane.bounds.width, pane.bounds.height),
                pane.source.upper(),
                self.COLOR_DIM,
                align="left",
            )
            return

        try:
            presenter.draw(draw, pane)
        except Exception:
            self._draw_text_box(
                draw,
                (pane.bounds.x, pane.bounds.y, pane.bounds.width, pane.bounds.height),
                "WIDGET ERR",
                self.COLOR_DOWN,
                align="left",
            )

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
        restart_on_end=True,
        align="center",
        force_scroll_pixels=0.0,
    ):
        state = {"at_end": False, "scrolling": False}
        if w <= 1 or h <= 1:
            return state

        txt = str(text or "").strip()
        if not txt:
            return state

        region = Image.new("RGB", (w, h), self.COLOR_BG)
        rd = ImageDraw.Draw(region)
        try:
            forced = max(0.0, float(force_scroll_pixels))
        except Exception:
            forced = 0.0

        visible_w = max(1, w - 2)
        font = self._font_for_box(rd, txt, visible_w, h, prefer_width_fit=not always_scroll)
        left, top, text_w, text_h = self._font_text_metrics(rd, txt, font)
        y_text = max(0, (h - text_h) // 2) - top
        if not always_scroll and text_w <= visible_w and forced <= 0.0:
            if align == "left":
                text_x = 1 - left
            elif align == "right":
                text_x = max(1, w - text_w - 1) - left
            else:
                text_x = max(1, (w - text_w) // 2) - left
            rd.text((text_x, y_text), txt, font=font, fill=color)
            self.canvas.paste(region, (x, y))
            return state

        state["scrolling"] = True

        # 1 px every N frames → uniform motion; N comes from SCROLL_SPEED.
        gap = 10
        color_key = tuple(color) if isinstance(color, (list, tuple)) else color
        render_key = (txt, color_key, h, id(font))
        strip = self._scroll_text_render_cache.get(render_key)
        if strip is None:
            strip = Image.new("RGB", (max(1, text_w), h), self.COLOR_BG)
            strip_draw = ImageDraw.Draw(strip)
            strip_draw.text((-left, y_text), txt, font=font, fill=color)
            self._scroll_text_render_cache[render_key] = strip

        cycle = strip.width + gap
        offset = self._scroll_offsets.get(key, 0.0)
        widget_name = str(key).split(":", 1)[0].split("-", 1)[0]
        step = 1.0 / scroll.frame_stride(widget_name)
        if wrap:
            offset = (offset + step) % cycle
        else:
            max_offset = max(0.0, float(strip.width - visible_w))
            if forced > 0.0:
                max_offset = max(max_offset, forced)
            offset = offset + step
            if offset > max_offset:
                state["at_end"] = True
                if restart_on_end:
                    offset = 0.0
                else:
                    offset = max_offset
            elif max_offset <= 0.0:
                state["at_end"] = True
        self._scroll_offsets[key] = offset

        if wrap:
            start_x = w - int(offset)
            region.paste(strip, (start_x, 0))
            region.paste(strip, (start_x - cycle, 0))
        else:
            start_x = 1 - int(offset)
            region.paste(strip, (start_x, 0))
        self.canvas.paste(region, (x, y))
        return state

    def _draw_scrolling_colored_ticker(self, x, y, w, h, parts, key, speed=16.0):
        if w <= 1 or h <= 1:
            return
        rendered_parts = []
        for text, color in parts or []:
            txt = str(text or "").strip()
            if not txt:
                continue
            rendered_parts.append((txt, color))
        if not rendered_parts:
            return

        gap = 8
        strip_w = gap
        probe = Image.new("RGB", (1, 1), self.COLOR_BG)
        probe_draw = ImageDraw.Draw(probe)
        font = self._font_for_box(probe_draw, " ".join(text for text, _ in rendered_parts), max(1, w - 2), h, prefer_width_fit=False)
        for txt, _color in rendered_parts:
            strip_w += int(font.getlength(txt)) + gap
        strip_w = max(strip_w, 1)

        strip = Image.new("RGB", (strip_w, h), self.COLOR_BG)
        sd = ImageDraw.Draw(strip)
        cx = gap // 2
        _left, top, _text_w, text_h = self._font_text_metrics(sd, "0", font)
        text_y = max(0, (h - text_h) // 2) - top
        for txt, color in rendered_parts:
            sd.text((cx, text_y), txt, font=font, fill=color)
            cx += int(font.getlength(txt)) + gap

        # 1 px every N frames → uniform motion; N comes from SCROLL_SPEED.
        widget_name = str(key).split(":", 1)[0].split("-", 1)[0]
        step = 1.0 / scroll.frame_stride(widget_name)
        cycle = strip_w + gap
        offset = self._scroll_offsets.get(key, 0.0)
        offset = (offset + step) % cycle
        self._scroll_offsets[key] = offset

        region = Image.new("RGB", (w, h), self.COLOR_BG)
        start_x = w - int(offset)
        region.paste(strip, (start_x, 0))
        region.paste(strip, (start_x - cycle, 0))
        self.canvas.paste(region, (x, y))

    def _draw_widget_metro(self, draw, x, y, w, h, scroll_mode="metro"):
        trains = getattr(self.metro, "trains", []) or []
        if not trains:
            self._draw_text_box(draw, (x, y, w, h), "NO TRAINS", self.COLOR_DIM, align="left")
            return

        mode = self._normalize_scroll_mode(scroll_mode, fallback="metro")
        if mode == "ticker":
            ticker_parts = []
            for row in trains:
                line = str(row.get("Line", "--")).upper()
                mins = str(row.get("Min", "--"))
                mins_label = f"{mins}M" if mins.isdigit() else mins
                dest = str(row.get("Destination", "Train") or "Train").upper()
                line_color = self.metro._line_color(line) if hasattr(self.metro, "_line_color") else self.COLOR_ACCENT
                ticker_parts.append((f"{line} {dest} {mins_label}".strip(), line_color))
            ticker_key = " | ".join(part[0] for part in ticker_parts)
            self._draw_scrolling_colored_ticker(
                x,
                y,
                w,
                h,
                ticker_parts,
                key=f"metro-mini:ticker:{ticker_key}",
                speed=float(getattr(self.metro, "scroll_speed", 20)),
            )
            return

        row = trains[self._metro_idx % len(trains)]
        line = str(row.get("Line", "--")).upper()
        mins = str(row.get("Min", "--"))
        dest = str(row.get("Destination", "Train") or "Train")

        line_color = self.metro._line_color(line) if hasattr(self.metro, "_line_color") else self.COLOR_ACCENT
        line_label = (line[:2] or "?").upper()
        line_font = self._font_for_box(draw, line_label, max(1, w // 3), h, prefer_width_fit=True)
        line_label_w = int(line_font.getlength(line_label))

        # Fixed left segment for line ID, like the main metro row "icon + static line".
        left_w = min(max(8, line_label_w + 4), max(8, w // 3))
        left_w = min(left_w, max(1, w - 6))
        right_w = max(1, w - left_w)

        line_x = x + max(1, (left_w - line_label_w) // 2)
        _left, top, _tw, line_h = self._font_text_metrics(draw, line_label, line_font)
        line_y = y + max(0, (h - line_h) // 2) - top
        draw.text((line_x, line_y), line_label, font=line_font, fill=line_color)

        mins_label = f"{mins}M" if mins.isdigit() else mins
        scroll_text = f"{dest.upper()} {mins_label}".strip()
        scroll_speed = float(getattr(self.metro, "scroll_speed", 20))
        scroll_key = f"metro-mini:{line}:{dest}:{mins}"
        scroll_state = self._draw_scrolling_text_clipped(
            x + left_w,
            y,
            right_w,
            h,
            scroll_text,
            self.COLOR_MAIN,
            key=scroll_key,
            speed=scroll_speed,
            **self._mini_scroll_args(mode, default_align="left"),
        )
        if not scroll_state.get("scrolling"):
            # If row text fits, still rotate through trains on a timer.
            now = time.time()
            if len(trains) > 1:
                if self._metro_mini_hold_key != "metro-static":
                    self._metro_mini_hold_key = "metro-static"
                    self._metro_mini_hold_started = now
                elif now - self._metro_mini_hold_started >= self._widget_rotate_seconds:
                    self._metro_idx = (self._metro_idx + 1) % len(trains)
                    self._metro_mini_hold_started = now
            return

        if scroll_state.get("at_end"):
            now = time.time()
            if self._metro_mini_hold_key != scroll_key:
                self._metro_mini_hold_key = scroll_key
                self._metro_mini_hold_started = now
            elif now - self._metro_mini_hold_started >= 1.2:
                if len(trains) > 1:
                    self._metro_idx = (self._metro_idx + 1) % len(trains)
                # Reset pass for same or next row.
                self._scroll_offsets[scroll_key] = 0.0
                self._metro_mini_hold_key = None
                self._metro_mini_hold_started = 0.0
        else:
            self._metro_mini_hold_key = None
            self._metro_mini_hold_started = 0.0

    def _pomodoro_state_for_clock(self):
        cached = self._pomodoro_state_cache
        if isinstance(cached, dict):
            return cached
        try:
            state = web_server.get_pomodoro_state() or {}
        except Exception:
            state = {}
        self._pomodoro_state_cache = state
        return state

    def _pomodoro_phase_style(self, phase):
        key = str(phase or "focus").strip().lower()
        if key == "focus":
            return {"label": "FOCUS", "color": self.COLOR_DOWN, "bg": self.COLOR_POMODORO_BG_FOCUS}
        if key == "long_break":
            return {"label": "LONG BREAK", "color": self.COLOR_UP, "bg": self.COLOR_POMODORO_BG_BREAK}
        return {"label": "BREAK", "color": self.COLOR_UP, "bg": self.COLOR_POMODORO_BG_BREAK}

    def _pomodoro_timer_text(self, remaining_seconds):
        total = max(0, int(remaining_seconds or 0))
        return f"{total // 60:02d}:{total % 60:02d}"

    def _draw_timer_text(self, draw, timer_text, *, x, y, w, h, color, bg_color, font=None):
        text = str(timer_text or "").strip()
        if not text:
            return

        selected_font = font or self._font_for_box(draw, text, max(1, w - 2), h, prefer_width_fit=True)
        if ":" not in text:
            fit = self._fit_text(text, max(1, w - 2), selected_font)
            text_w = int(selected_font.getlength(fit))
            _left, top, _tw, font_h = self._font_text_metrics(draw, fit, selected_font)
            y_off = max(0, (h - font_h) // 2)
            draw.text((x + max(0, (w - text_w) // 2), y + y_off - top), fit, font=selected_font, fill=color)
            return

        mins, secs = text.split(":", 1)
        mins = mins.strip()
        secs = secs.strip()
        if not mins or not secs:
            fit = self._fit_text(text, max(1, w - 2), selected_font)
            text_w = int(selected_font.getlength(fit))
            _left, top, _tw, font_h = self._font_text_metrics(draw, fit, selected_font)
            y_off = max(0, (h - font_h) // 2)
            draw.text((x + max(0, (w - text_w) // 2), y + y_off - top), fit, font=selected_font, fill=color)
            return

        mins_w = int(selected_font.getlength(mins))
        secs_w = int(selected_font.getlength(secs))
        _left, top, _tw, selected_h = self._font_text_metrics(draw, text, selected_font)
        strip_h = max(1, selected_h)
        strip_w = max(1, mins_w + 2 + secs_w)
        if strip_w > max(1, w - 1) and selected_font is not self.font_small:
            self._draw_timer_text(
                draw,
                text,
                x=x,
                y=y,
                w=w,
                h=h,
                color=color,
                bg_color=bg_color,
                font=self.font_small,
            )
            return

        strip = Image.new("RGB", (strip_w, strip_h), bg_color)
        strip_draw = ImageDraw.Draw(strip)
        cursor = 0
        strip_draw.text((cursor, -top), mins, font=selected_font, fill=color)
        cursor += mins_w
        if strip_h >= 10:
            strip_draw.point((cursor, max(1, strip_h // 3)), fill=color)
            strip_draw.point((cursor, max(1, (strip_h * 2) // 3)), fill=color)
        else:
            # Small-size timer keeps a single-dot colon to avoid crowding.
            strip_draw.point((cursor, max(1, strip_h // 2)), fill=color)
        cursor += 2
        strip_draw.text((cursor, -top), secs, font=selected_font, fill=color)

        paste_x = x + max(0, (w - strip.width) // 2)
        paste_y = y + max(0, (h - strip.height) // 2)
        self.canvas.paste(strip, (paste_x, paste_y))

    def _wrap_text_lines(self, text, max_width, font, max_lines=2):
        normalized = " ".join(str(text or "").strip().split())
        if not normalized or max_width <= 0 or max_lines <= 0:
            return []

        words = normalized.split(" ")
        lines = []
        idx = 0
        while idx < len(words) and len(lines) < int(max_lines):
            token = words[idx]
            idx += 1
            if int(font.getlength(token)) > max_width:
                lines.append(self._fit_text(token, max_width, font))
                continue

            line = token
            while idx < len(words):
                candidate = f"{line} {words[idx]}"
                if int(font.getlength(candidate)) <= max_width:
                    line = candidate
                    idx += 1
                    continue
                break
            lines.append(line)

        if idx < len(words) and lines:
            lines[-1] = self._fit_text(f"{lines[-1]} ...", max_width, font)
        return [line for line in lines if line]

    def _compact_pomodoro_value_bounds(self, x, y, w, h):
        return x, y + 1, w, max(1, h - 1)

    def _draw_compact_pomodoro_value(self, draw, x, y, w, h, running, remaining_seconds, bg_color):
        value_x, value_y, value_w, value_h = self._compact_pomodoro_value_bounds(x, y, w, h)
        if running:
            self._draw_timer_text(
                draw,
                self._pomodoro_timer_text(remaining_seconds),
                x=value_x,
                y=value_y,
                w=value_w,
                h=value_h,
                color=self.COLOR_MAIN,
                bg_color=bg_color,
            )
            return

        self._draw_text_box(draw, (value_x, value_y, value_w, value_h), "PAUSED", self.COLOR_MAIN)

    def _draw_widget_pomodoro(self, draw, x, y, w, h, focused=False):
        if w <= 0 or h <= 0:
            return

        state = self._pomodoro_state_for_clock()
        phase_style = self._pomodoro_phase_style(state.get("phase"))
        phase_label = phase_style["label"]
        phase_color = phase_style["color"]
        phase_bg = phase_style["bg"]
        running = bool(state.get("running", False))

        if not focused:
            draw.rectangle((x, y, x + w - 1, y + h - 1), fill=phase_bg)
            self._draw_compact_pomodoro_value(
                draw,
                x=x,
                y=y,
                w=w,
                h=h,
                running=running,
                remaining_seconds=state.get("remaining_seconds", 0),
                bg_color=phase_bg,
            )
            return

        self._draw_text_box(draw, (x, y, w, 8), phase_label, phase_color)

        layout = str(state.get("layout", "mode_time_task") or "mode_time_task").strip().lower()
        show_task = layout != "mode_time"
        timer_txt = self._pomodoro_timer_text(state.get("remaining_seconds", 0)) if running else "PAUSED"

        if show_task:
            timer_y = y + 8
            timer_h = min(10, max(6, h - 14))
        else:
            timer_y = y + 9
            timer_h = max(8, h - 12)

        if running:
            self._draw_timer_text(
                draw,
                timer_txt,
                x=x,
                y=timer_y,
                w=w,
                h=timer_h,
                color=self.COLOR_MAIN,
                bg_color=self.COLOR_BG,
            )
        else:
            paused_font = self._font_for_box(draw, timer_txt, max(1, w - 2), timer_h, prefer_width_fit=True)
            paused = self._fit_text(timer_txt, max(1, w - 2), paused_font)
            paused_w = int(paused_font.getlength(paused))
            _left, top, _tw, paused_h = self._font_text_metrics(draw, paused, paused_font)
            paused_y = timer_y + max(0, (timer_h - paused_h) // 2) - top
            draw.text((x + max(0, (w - paused_w) // 2), paused_y), paused, font=paused_font, fill=self.COLOR_MAIN)

        if not show_task:
            return

        task = str(state.get("current_task", "") or "").strip()
        task_top = y + 18
        task_h = max(6, y + h - task_top)
        max_lines = 2 if task_h >= 12 else 1

        if task:
            task_font = self._font_for_box(draw, task.upper(), max(1, w - 2), max(1, task_h // max_lines), prefer_width_fit=False)
            task_lines = self._wrap_text_lines(task.upper(), max(1, w - 2), task_font, max_lines=max_lines)
            task_color = self.COLOR_ACCENT
        else:
            task_font = self._font_for_box(draw, "NO TASK", max(1, w - 2), max(1, task_h), prefer_width_fit=True)
            task_lines = ["NO TASK"]
            task_color = self.COLOR_DIM

        if not task_lines:
            return

        _left, top, _tw, line_h = self._font_text_metrics(draw, "0", task_font)
        visible_lines = task_lines[: max(1, task_h // line_h)]
        total_h = max(1, len(visible_lines) * line_h)
        start_y = task_top + max(0, (task_h - total_h) // 2)
        for idx, line in enumerate(visible_lines):
            line_w = int(task_font.getlength(line))
            draw.text(
                (x + max(0, (w - line_w) // 2), start_y + idx * line_h - top),
                line,
                font=task_font,
                fill=task_color,
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
            self._draw_text_box(draw, (x, y, w, h), "WEATHER", self.COLOR_DIM, align="left")
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
            self._draw_text_box(draw, (x, y + icon_h, w, max(1, h - icon_h - 7)), temp_text, self.COLOR_MAIN)

            if h >= 24:
                self._draw_text_box(draw, (x, y + h - 8, w, 8), label, self.COLOR_ACCENT)
            return

        unit_raw = str(getattr(config, "WEATHER_UNITS", "metric") or "metric").strip().lower()
        unit_suffix = "F" if unit_raw in {"imperial", "f", "fahrenheit"} else "C"
        text = f"{temp}\N{DEGREE SIGN}{unit_suffix}"
        self._draw_text_box(draw, (x, y, w, h), text, self.COLOR_MAIN)

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

    def _draw_widget_stocks(self, draw, x, y, w, h, focused=False, scroll_mode="metro"):
        symbols = self._stock_symbols()
        if not symbols:
            self._draw_text_box(draw, (x, y, w, h), "NO STOCKS", self.COLOR_DIM, align="left")
            return

        if focused:
            symbol = symbols[self._stock_idx % len(symbols)]
            data = self._stock_data(symbol, "1D")
            self._draw_text_box(draw, (x, y, w, min(14, h)), symbol, self.COLOR_MAIN)
            if not data or data.get("last_price") is None:
                self._draw_text_box(draw, (x, y + h - 8, w, 8), "...", self.COLOR_DIM)
                return

            last = data.get("last_price")
            prev = data.get("prev_close")
            change = self.stocks._change(last, prev) if hasattr(self.stocks, "_change") else 0.0
            pct = self.stocks._fmt_pct(last, prev, signed=False) if hasattr(self.stocks, "_fmt_pct") else "--%"
            price = self.stocks._fmt_price(last) if hasattr(self.stocks, "_fmt_price") else str(last)
            color = self.COLOR_UP if change >= 0 else self.COLOR_DOWN

            self._draw_text_box(draw, (x, y + 13, w, max(1, h - 21)), price, self.COLOR_MAIN)
            self._draw_text_box(draw, (x, y + h - 8, w, 8), pct, color)
            return

        # Horizontal split stock ticker (mini).
        mode = self._normalize_scroll_mode(scroll_mode, fallback="metro")
        if mode == "metro":
            symbol = symbols[self._stock_idx % len(symbols)]
            data = self._stock_data(symbol, "1D")
            if not data or data.get("last_price") is None:
                self._draw_text_box(draw, (x, y, w, h), "STOCKS LOADING", self.COLOR_DIM, align="left")
                return

            last = data.get("last_price")
            prev = data.get("prev_close")
            change = self.stocks._change(last, prev) if hasattr(self.stocks, "_change") else 0.0
            price = self.stocks._fmt_price(last) if hasattr(self.stocks, "_fmt_price") else str(last)
            pct = self.stocks._fmt_pct(last, prev, signed=False) if hasattr(self.stocks, "_fmt_pct") else "--%"
            text = f"{symbol} {price} {pct}"
            color = self.COLOR_UP if change >= 0 else self.COLOR_DOWN
            scroll_key = f"stocks-mini:metro:{symbol}"
            if self._stocks_mini_last_symbol != symbol:
                self._stocks_mini_last_symbol = symbol
                self._scroll_offsets[scroll_key] = 0.0
                self._scroll_last_ts[scroll_key] = time.time()

            scroll_args = self._mini_scroll_args(mode, default_align="left")
            scroll_args["force_scroll_pixels"] = max(12.0, float(w) * 0.35)
            scroll_state = self._draw_scrolling_text_clipped(
                x,
                y,
                w,
                h,
                text,
                color,
                key=scroll_key,
                speed=18.0,
                **scroll_args,
            )

            if scroll_state.get("at_end"):
                now = time.time()
                if self._stocks_mini_hold_key != scroll_key:
                    self._stocks_mini_hold_key = scroll_key
                    self._stocks_mini_hold_started = now
                elif now - self._stocks_mini_hold_started >= 1.0:
                    if len(symbols) > 1:
                        self._stock_idx = (self._stock_idx + 1) % len(symbols)
                        self._last_widget_rotate = now
                    self._scroll_offsets[scroll_key] = 0.0
                    self._stocks_mini_last_symbol = None
                    self._stocks_mini_hold_key = None
                    self._stocks_mini_hold_started = 0.0
            else:
                self._stocks_mini_hold_key = None
                self._stocks_mini_hold_started = 0.0
            return

        parts = []
        for sym in symbols:
            data = self._stock_data(sym, "1D")
            if not data or data.get("last_price") is None:
                continue
            last = data.get("last_price")
            prev = data.get("prev_close")
            change = self.stocks._change(last, prev) if hasattr(self.stocks, "_change") else 0.0
            price = self.stocks._fmt_price(last) if hasattr(self.stocks, "_fmt_price") else str(last)
            pct = self.stocks._fmt_pct(last, prev, signed=False) if hasattr(self.stocks, "_fmt_pct") else "--%"
            color = self.COLOR_UP if change >= 0 else self.COLOR_DOWN
            parts.append((f"{sym} {price} {pct}", color))

        if not parts:
            self._draw_text_box(draw, (x, y, w, h), "STOCKS LOADING", self.COLOR_DIM, align="left")
            return

        ticker_key = " | ".join(text for text, _color in parts)
        self._draw_scrolling_colored_ticker(
            x,
            y,
            w,
            h,
            parts,
            key=f"stocks:ticker:{ticker_key}",
            speed=18.0,
        )

    def _draw_widget_flight(self, draw, x, y, w, h, scroll_mode="metro"):
        data = getattr(self.flight, "data", None)
        if not data:
            txt = str(getattr(self.flight, "status_text", "FLIGHT")).upper()
            self._draw_text_box(draw, (x, y, w, h), txt, self.COLOR_DIM, align="left")
            return

        flight_no = str((data.get("flight") or {}).get("iata") or getattr(config, "FLIGHT_NUMBER", "FLIGHT")).upper()
        status = str(data.get("flight_status", "") or "").upper()
        text = f"{flight_no} {status}"
        self._draw_scrolling_text_clipped(
            x,
            y,
            w,
            h,
            text,
            self.COLOR_MAIN,
            key=f"flight-mini:{text}",
            speed=14.0,
            **self._mini_scroll_args(scroll_mode, default_align="left"),
        )

    def _draw_widget_sports(self, draw, x, y, w, h, focused=False, scroll_mode="metro"):
        games = getattr(self.sports, "games", []) or []
        if not games:
            self._draw_text_box(draw, (x, y, w, h), "NO GAMES", self.COLOR_DIM, align="left")
            return

        idx = getattr(self.sports, "current_game_index", 0) % len(games)
        game = games[idx]
        away = game.get("away", {})
        home = game.get("home", {})

        if focused:
            status = self.sports._status_text(game) if hasattr(self.sports, "_status_text") else "LIVE"
            status_band_h = 8
            self._draw_text_box(draw, (x, y, w, status_band_h), status, self.COLOR_DIM)

            row_gap = 2
            row_h = max(8, (h - status_band_h - row_gap) // 2)
            away_y = y + status_band_h
            home_y = away_y + row_h
            bar_w = 2

            def draw_team_row(team, other, side, row_y):
                team_color = tuple(team.get("color") or self.COLOR_ACCENT)
                draw.rectangle((x, row_y + 1, x + bar_w - 1, min(y + h - 1, row_y + row_h - 1)), fill=team_color)

                score = str(team.get("score", 0))
                score_font = self._font_for_box(draw, score, max(1, w // 4), row_h, prefer_width_fit=True)
                score_w = int(score_font.getlength(score))
                score_x = x + w - score_w - 1
                _left, score_top, _tw, score_h = self._font_text_metrics(draw, score, score_font)
                score_y = row_y + max(0, (row_h - score_h) // 2) - score_top
                draw.text((score_x, score_y), score, font=score_font, fill=self.COLOR_MAIN)

                name_x = x + bar_w + 2
                name_max_w = max(1, score_x - name_x - 1)
                name_raw = str(team.get("abbr", "---"))
                name_font = self._font_for_box(draw, name_raw, name_max_w, row_h, prefer_width_fit=True)
                name = self._fit_text(name_raw, name_max_w, name_font)
                _left, name_top, _tw, name_h = self._font_text_metrics(draw, name, name_font)
                name_y = row_y + max(0, (row_h - name_h) // 2) - name_top
                draw.text((name_x, name_y), name, font=name_font, fill=team_color)

                if game.get("possession") == side and hasattr(self.sports, "_draw_possession_arrow"):
                    arrow_x = name_x + int(name_font.getlength(name)) + 1
                    if arrow_x + 3 < score_x:
                        self.sports._draw_possession_arrow(draw, arrow_x, row_y + 2)

            draw_team_row(away, home, "away", away_y)
            draw_team_row(home, away, "home", home_y)
            return

        mode = self._normalize_scroll_mode(scroll_mode, fallback="metro")
        if mode == "ticker":
            ticker_parts = []
            for row in games:
                away_team = str((row.get("away") or {}).get("abbr", "AWY")).upper()
                home_team = str((row.get("home") or {}).get("abbr", "HME")).upper()
                row_status = self.sports._status_text(row) if hasattr(self.sports, "_status_text") else ""
                ticker_parts.append(f"{away_team} v. {home_team} {row_status}".strip())
            ticker = "   ".join(ticker_parts)
            self._draw_scrolling_text_clipped(
                x,
                y,
                w,
                h,
                ticker,
                self.COLOR_MAIN,
                key=f"sports-mini:ticker:{ticker}",
                speed=20.0,
                **self._mini_scroll_args(mode, default_align="left"),
            )
            return

        away_abbr = str(away.get("abbr", "AWY")).upper()
        home_abbr = str(home.get("abbr", "HME")).upper()
        status = self.sports._status_text(game) if hasattr(self.sports, "_status_text") else ""
        scroll_text = f"{away_abbr} v. {home_abbr} {status}".strip()
        game_id = str(game.get("id", ""))
        stable_id = game_id or f"{away_abbr}-{home_abbr}"
        scroll_key = f"sports-mini:{stable_id}"

        scroll_state = self._draw_scrolling_text_clipped(
            x,
            y,
            w,
            h,
            scroll_text,
            self.COLOR_MAIN,
            key=scroll_key,
            speed=20.0,
            **self._mini_scroll_args(mode, default_align="left"),
        )
        if not scroll_state.get("scrolling"):
            # If the line fits without scrolling, still rotate games on a timer.
            now = time.time()
            if len(games) > 1:
                if self._sports_mini_hold_key != "sports-static":
                    self._sports_mini_hold_key = "sports-static"
                    self._sports_mini_hold_started = now
                elif now - self._sports_mini_hold_started >= self._widget_rotate_seconds:
                    self.sports.current_game_index = (idx + 1) % len(games)
                    if hasattr(self.sports, "last_rotate"):
                        self.sports.last_rotate = now
                    self._sports_mini_hold_started = now
            return

        if scroll_state.get("at_end"):
            now = time.time()
            if self._sports_mini_hold_key != scroll_key:
                self._sports_mini_hold_key = scroll_key
                self._sports_mini_hold_started = now
            elif now - self._sports_mini_hold_started >= 1.2:
                if len(games) > 1:
                    self.sports.current_game_index = (idx + 1) % len(games)
                    if hasattr(self.sports, "last_rotate"):
                        self.sports.last_rotate = now
                # Restart pass for same/next game.
                self._scroll_offsets[scroll_key] = 0.0
                self._sports_mini_hold_key = None
                self._sports_mini_hold_started = 0.0
        else:
            self._sports_mini_hold_key = None
            self._sports_mini_hold_started = 0.0

    # --------------------------------------------------------------- utils

    def _fit_text(self, text, max_width, font, ellipsis="..."):
        if not text:
            return ""
        txt = str(text)
        if int(font.getlength(txt)) <= max_width:
            return txt
        while txt and int(font.getlength(txt + ellipsis)) > max_width:
            txt = txt[:-1]
        return (txt + ellipsis) if txt else ""
