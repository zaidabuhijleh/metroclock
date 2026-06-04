from __future__ import annotations

import time
import traceback
from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Protocol

import config
import web_server
from core.display import Display
from core.modes import DEFAULT_MODE_CATALOG, ModeCatalog
from core.widget import Widget
from widgets.ambient import AmbientWidget
from widgets.clock import ClockWidget
from widgets.flight import FlightWidget
from widgets.metro import MetroWidget
from widgets.pomodoro import PomodoroWidget
from widgets.sports import SportsWidget
from widgets.stocks import StocksWidget
from widgets.weather import WeatherWidget


class RuntimeStateProvider(Protocol):
    def get_display_mode(self) -> str:
        ...

    def get_brightness(self) -> int:
        ...


@dataclass(frozen=True)
class DisplayHardwareProfile:
    width: int
    height: int
    slowdown: int
    brightness: int


class ModePwmBitsResolver:
    """Resolves per-mode PWM values with sane clamping/fallbacks."""

    def __init__(
        self,
        fallback_bits: Optional[int] = None,
        defaults: Optional[Mapping[str, int]] = None,
        mode_catalog: ModeCatalog = DEFAULT_MODE_CATALOG,
    ):
        self._fallback_bits = fallback_bits if fallback_bits is not None else getattr(config, "MATRIX_PWM_BITS", 3)
        self._defaults = dict(defaults or {})
        self._mode_catalog = mode_catalog

    def resolve(self, mode: str) -> int:
        mode_key = str(mode or "").strip().lower()
        fallback = self._clamp_pwm_bits(self._fallback_bits)
        config_key = f"MATRIX_PWM_BITS_{mode_key.upper()}" if mode_key else ""
        default_bits = self._defaults.get(mode_key, self._mode_catalog.default_pwm_bits_for(mode_key, fallback))
        configured = getattr(config, config_key, default_bits)
        return self._safe_pwm_bits(configured, fallback)

    @staticmethod
    def _safe_pwm_bits(value, fallback: int) -> int:
        try:
            parsed = int(value)
        except Exception:
            parsed = int(fallback)
        return ModePwmBitsResolver._clamp_pwm_bits(parsed)

    @staticmethod
    def _clamp_pwm_bits(value: int) -> int:
        return max(1, min(11, int(value)))


class DisplayManager:
    """Owns the hardware display lifecycle and mode-specific options."""

    def __init__(self, hardware: DisplayHardwareProfile, pwm_resolver: Optional[ModePwmBitsResolver] = None):
        self._hardware = hardware
        self._pwm_resolver = pwm_resolver or ModePwmBitsResolver()
        self._display: Optional[Display] = None
        self._active_pwm_bits: Optional[int] = None

    def ensure_mode(self, mode: str):
        target_pwm_bits = self._pwm_resolver.resolve(mode)
        if self._display is not None and target_pwm_bits == self._active_pwm_bits:
            return

        self._display = Display(
            width=self._hardware.width,
            height=self._hardware.height,
            slowdown=self._hardware.slowdown,
            brightness=self._hardware.brightness,
            pwm_bits=target_pwm_bits,
        )
        self._active_pwm_bits = target_pwm_bits
        print(f"Display mode={mode}, pwm_bits={target_pwm_bits}")

    def present(self, image, brightness: int):
        if self._display is None:
            raise RuntimeError("Display has not been initialized")
        self._display.clear()
        self._display.set_brightness(brightness)
        self._display.draw_image(image)
        self._display.push()


class WidgetRenderer:
    """Wraps a widget with a uniform render lifecycle."""

    def __init__(self, widget: Widget):
        self.widget = widget

    def render(self):
        self.widget.update()
        return self.widget.draw()


class WidgetRegistry:
    """Constructs and owns all widget instances and mode routing."""

    def __init__(self, width: int, height: int, mode_catalog: ModeCatalog = DEFAULT_MODE_CATALOG):
        self._mode_catalog = mode_catalog
        self.metro = MetroWidget(width, height)
        self.weather = WeatherWidget(width, height)
        self.flight = FlightWidget(width, height)
        self.ambient = AmbientWidget(width, height)
        self.sports = SportsWidget(width, height)
        self.stocks = StocksWidget(width, height)
        self.pomodoro = PomodoroWidget(width, height)
        self.clock = ClockWidget(
            width,
            height,
            self.metro,
            self.weather,
            self.flight,
            self.sports,
            self.stocks,
        )

        self._renderers: Dict[str, WidgetRenderer] = {
            "metro": WidgetRenderer(self.metro),
            "weather": WidgetRenderer(self.weather),
            "flight": WidgetRenderer(self.flight),
            "ambient": WidgetRenderer(self.ambient),
            "sports": WidgetRenderer(self.sports),
            "stocks": WidgetRenderer(self.stocks),
            "pomodoro": WidgetRenderer(self.pomodoro),
            "clock": WidgetRenderer(self.clock),
        }

    def render_mode(self, mode: str):
        widget_key = self._mode_catalog.widget_key_for(mode, fallback="clock")
        renderer = self._renderers.get(widget_key, self._renderers["clock"])
        return renderer.render()


class MetroClockApp:
    """Top-level dashboard application object."""

    def __init__(
        self,
        state_provider: RuntimeStateProvider,
        widgets: WidgetRegistry,
        display: DisplayManager,
        loop_delay: float = 0.02,
        error_delay: float = 0.25,
    ):
        self._state_provider = state_provider
        self._widgets = widgets
        self._display = display
        self._loop_delay = loop_delay
        self._error_delay = error_delay

    @classmethod
    def build_default(cls) -> "MetroClockApp":
        hardware = DisplayHardwareProfile(
            width=config.MATRIX_WIDTH,
            height=config.MATRIX_HEIGHT,
            slowdown=config.MATRIX_SLOWDOWN,
            brightness=config.MATRIX_BRIGHTNESS,
        )
        display = DisplayManager(hardware=hardware)
        widgets = WidgetRegistry(width=config.MATRIX_WIDTH, height=config.MATRIX_HEIGHT)
        return cls(state_provider=web_server, widgets=widgets, display=display)

    def run_forever(self):
        web_server.start_server()
        print("Dashboard Started. Press Ctrl+C to exit.")

        try:
            while True:
                self._tick()
        except KeyboardInterrupt:
            print("\nExiting...")

    def _tick(self):
        mode = self._state_provider.get_display_mode()
        try:
            self._display.ensure_mode(mode)
            frame = self._widgets.render_mode(mode)
            brightness = self._state_provider.get_brightness()
            self._display.present(frame, brightness)
            web_server.set_latest_frame(frame)
            time.sleep(self._loop_delay)
        except Exception as exc:
            print(f"Render loop error ({mode}): {exc}")
            traceback.print_exc()
            time.sleep(self._error_delay)
