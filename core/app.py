from __future__ import annotations

import time
import traceback
from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Protocol

from PIL import Image

import config
import web_server
from core.boot_splash import render_boot_splash
from core.display import Display
from core.modes import DEFAULT_MODE_CATALOG, ModeCatalog
from core.status_frame import render_status_frame
from core.widget import Widget
from widgets.ambient import AmbientWidget
from widgets.clock import ClockWidget
from widgets.custom import CustomWidget
from widgets.flight import FlightWidget
from widgets.metro import MetroWidget
from widgets.pairing_status import PairingStatusWidget
from widgets.pomodoro import PomodoroWidget
from widgets.setup_status import SetupStatusWidget
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
        print(f"Display mode={mode}, pwm_bits={target_pwm_bits}", flush=True)

    def present(self, image, brightness: int):
        if self._display is None:
            raise RuntimeError("Display has not been initialized")
        self._display.set_brightness(brightness)
        self._display.draw_image(image)
        self._display.push()

    def status_frame(self, lines):
        return render_status_frame(self._hardware.width, self._hardware.height, lines)

    def present_status(self, lines, brightness: int, mode: str = "setup"):
        self.ensure_mode(mode)
        frame = self.status_frame(lines)
        self.present(frame, brightness)
        return frame

    def boot_splash_frame(self):
        return render_boot_splash(self._hardware.width, self._hardware.height)

    def present_boot_splash(self, brightness: int, mode: str = "setup"):
        self.ensure_mode(mode)
        frame = self.boot_splash_frame()
        self.present(frame, brightness)
        return frame


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
        self.setup = SetupStatusWidget(width, height, web_server.get_wifi_setup_status)
        self.pairing = PairingStatusWidget(width, height)
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
        self.custom = CustomWidget(
            width,
            height,
            self.metro,
            self.weather,
            self.flight,
            self.sports,
            self.stocks,
        )

        self._renderers: Dict[str, WidgetRenderer] = {
            "setup": WidgetRenderer(self.setup),
            "pairing": WidgetRenderer(self.pairing),
            "metro": WidgetRenderer(self.metro),
            "weather": WidgetRenderer(self.weather),
            "flight": WidgetRenderer(self.flight),
            "ambient": WidgetRenderer(self.ambient),
            "sports": WidgetRenderer(self.sports),
            "stocks": WidgetRenderer(self.stocks),
            "pomodoro": WidgetRenderer(self.pomodoro),
            "clock": WidgetRenderer(self.clock),
            "custom": WidgetRenderer(self.custom),
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
        wifi_setup_manager=None,
        cloud_agent=None,
        loop_delay: float = 0.02,
        error_delay: float = 0.25,
        boot_splash_started_at: Optional[float] = None,
        minimum_boot_splash_seconds: float = 2.0,
    ):
        self._state_provider = state_provider
        self._widgets = widgets
        self._display = display
        self._wifi_setup_manager = wifi_setup_manager
        self._cloud_agent = cloud_agent
        self._loop_delay = loop_delay
        self._error_delay = error_delay
        self._boot_splash_started_at = boot_splash_started_at
        self._minimum_boot_splash_seconds = minimum_boot_splash_seconds
        self._last_mode = None
        self._last_perf_log = 0.0
        self._last_error_frame_at = 0.0
        self._last_error_signature = None
        self._last_blank_frame_log = 0.0
        self._last_presented_frame = None
        self._displayed_mode = None
        self._crossfade_excluded_modes = {"metro", "stocks"}

    @classmethod
    def build_default(cls) -> "MetroClockApp":
        hardware = DisplayHardwareProfile(
            width=config.MATRIX_WIDTH,
            height=config.MATRIX_HEIGHT,
            slowdown=config.MATRIX_SLOWDOWN,
            brightness=config.MATRIX_BRIGHTNESS,
        )
        display = DisplayManager(hardware=hardware)
        boot_splash_started_at = None
        try:
            frame = display.present_boot_splash(hardware.brightness)
            web_server.set_latest_frame(frame)
            boot_splash_started_at = time.monotonic()
        except Exception as exc:
            print(f"Startup splash frame failed: {exc}", flush=True)
        widgets = WidgetRegistry(width=config.MATRIX_WIDTH, height=config.MATRIX_HEIGHT)
        try:
            from core.wifi_setup import WifiSetupManager

            wifi_setup_manager = WifiSetupManager()
        except Exception as exc:
            print(f"WiFi setup manager disabled: {exc}")
            wifi_setup_manager = None
        try:
            from core.cloud_agent import MetroClockCloudAgent

            cloud_agent = MetroClockCloudAgent()
        except Exception as exc:
            print(f"Cloud agent disabled: {exc}")
            cloud_agent = None
        return cls(
            state_provider=web_server,
            widgets=widgets,
            display=display,
            wifi_setup_manager=wifi_setup_manager,
            cloud_agent=cloud_agent,
            boot_splash_started_at=boot_splash_started_at,
        )

    def run_forever(self):
        if self._wifi_setup_manager is not None:
            web_server.set_wifi_setup_manager(self._wifi_setup_manager)
            self._wifi_setup_manager.start()
        web_server.start_server()
        if self._cloud_agent is not None:
            self._cloud_agent.start()
        self._hold_boot_splash_if_needed()
        print("Dashboard Started. Press Ctrl+C to exit.", flush=True)

        try:
            while True:
                self._tick()
        except KeyboardInterrupt:
            print("\nExiting...")

    def _hold_boot_splash_if_needed(self):
        if self._boot_splash_started_at is None:
            return
        remaining = self._minimum_boot_splash_seconds - (time.monotonic() - self._boot_splash_started_at)
        if remaining > 0:
            time.sleep(remaining)

    def _tick(self):
        mode = "unknown"
        try:
            mode = self._state_provider.get_display_mode()
            if self._wifi_setup_manager is not None and self._wifi_setup_manager.should_show_setup_message():
                mode = "setup"
            elif self._should_show_pairing_message():
                mode = "pairing"
            tick_start = time.perf_counter()
            frame = self._widgets.render_mode(mode)
            if self._is_blank_frame(frame):
                self._log_blank_frame(mode)
                frame = self._display.status_frame(("NO CONTENT", mode, "FRAME BLANK"))
            rendered_at = time.perf_counter()
            self._display.ensure_mode(mode)
            ensured_at = time.perf_counter()
            brightness = self._state_provider.get_brightness()
            self._present_frame(mode, frame, brightness)
            presented_at = time.perf_counter()
            web_server.set_latest_frame(frame)
            self._log_perf_if_needed(mode, tick_start, ensured_at, rendered_at, presented_at)
            time.sleep(self._loop_delay)
        except Exception as exc:
            print(f"Render loop error ({mode}): {exc}", flush=True)
            traceback.print_exc()
            self._present_error_frame(mode, exc)
            time.sleep(self._error_delay)

    def _present_frame(self, mode: str, frame, brightness: int):
        previous_frame = self._last_presented_frame
        mode_changed = self._displayed_mode is not None and mode != self._displayed_mode
        should_crossfade = mode_changed and mode not in self._crossfade_excluded_modes
        if should_crossfade and self._can_crossfade(previous_frame, frame):
            self._crossfade(previous_frame, frame, brightness)
        else:
            self._display.present(frame, brightness)

        try:
            self._last_presented_frame = frame.copy()
        except Exception:
            self._last_presented_frame = None
        self._displayed_mode = mode

    @staticmethod
    def _can_crossfade(previous_frame, next_frame) -> bool:
        return (
            isinstance(previous_frame, Image.Image)
            and isinstance(next_frame, Image.Image)
            and previous_frame.size == next_frame.size
        )

    def _crossfade(self, previous_frame, next_frame, brightness: int):
        previous = previous_frame.convert("RGB")
        next_image = next_frame.convert("RGB")
        steps = 5
        delay = 0.03

        for step in range(1, steps + 1):
            alpha = step / steps
            blended = Image.blend(previous, next_image, alpha)
            self._display.present(blended, brightness)
            if step < steps:
                time.sleep(delay)

    def _present_error_frame(self, mode: str, exc: Exception):
        now = time.time()
        signature = (str(mode), type(exc).__name__, str(exc)[:64])
        if signature == self._last_error_signature and now - self._last_error_frame_at < 5.0:
            return

        try:
            frame = self._display.present_status(
                ("RENDER ERR", str(mode or "UNKNOWN"), str(exc) or type(exc).__name__),
                self._fallback_brightness(),
            )
            web_server.set_latest_frame(frame)
            self._last_error_frame_at = now
            self._last_error_signature = signature
        except Exception as status_exc:
            print(f"Error status frame failed: {status_exc}", flush=True)

    @staticmethod
    def _fallback_brightness() -> int:
        try:
            return int(web_server.get_brightness())
        except Exception:
            return int(getattr(config, "MATRIX_BRIGHTNESS", 100))

    @staticmethod
    def _should_show_pairing_message() -> bool:
        return not str(getattr(config, "METROCLOCK_CLOUD_DEVICE_TOKEN", "") or "").strip()

    @staticmethod
    def _is_blank_frame(frame) -> bool:
        try:
            return frame.getbbox() is None
        except Exception:
            return False

    def _log_blank_frame(self, mode: str):
        now = time.time()
        if now - self._last_blank_frame_log < 5.0:
            return
        print(f"Blank frame from mode={mode}; showing fallback status", flush=True)
        self._last_blank_frame_log = now

    def _log_perf_if_needed(self, mode, tick_start, ensured_at, rendered_at, presented_at):
        total_ms = (presented_at - tick_start) * 1000.0
        now = time.time()
        mode_changed = mode != self._last_mode
        slow_frame = total_ms >= 80.0
        periodic_custom = mode == "clock_widget" and now - self._last_perf_log >= 2.0
        if not (mode_changed or slow_frame or periodic_custom):
            return

        print(
            "PERF "
            f"mode={mode} "
            f"total={total_ms:.1f}ms "
            f"render={(rendered_at - tick_start) * 1000.0:.1f}ms "
            f"ensure={(ensured_at - rendered_at) * 1000.0:.1f}ms "
            f"present={(presented_at - ensured_at) * 1000.0:.1f}ms",
            flush=True,
        )
        self._last_mode = mode
        self._last_perf_log = now
