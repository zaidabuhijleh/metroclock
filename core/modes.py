from dataclasses import dataclass
from typing import Dict, Iterable, Tuple


@dataclass(frozen=True)
class DisplayMode:
    key: str
    widget_key: str
    default_pwm_bits: int


class ModeCatalog:
    """Registry of supported display modes and their widget bindings."""

    def __init__(self, modes: Iterable[DisplayMode]):
        self._modes: Dict[str, DisplayMode] = {mode.key: mode for mode in modes}

    def normalize(self, mode: str, fallback: str = "clock") -> str:
        key = str(mode or "").strip().lower()
        return key if key in self._modes else fallback

    def is_supported(self, mode: str) -> bool:
        key = str(mode or "").strip().lower()
        return key in self._modes

    def widget_key_for(self, mode: str, fallback: str = "clock") -> str:
        normalized = self.normalize(mode, fallback=fallback)
        mode_info = self._modes.get(normalized)
        return mode_info.widget_key if mode_info else fallback

    def default_pwm_bits_for(self, mode: str, fallback: int) -> int:
        key = str(mode or "").strip().lower()
        mode_info = self._modes.get(key)
        return mode_info.default_pwm_bits if mode_info else fallback

    @property
    def keys(self) -> Tuple[str, ...]:
        return tuple(self._modes.keys())


DEFAULT_MODE_CATALOG = ModeCatalog(
    modes=(
        DisplayMode("metro", "metro", 3),
        DisplayMode("weather", "weather", 5),
        DisplayMode("flight", "flight", 3),
        DisplayMode("ambient", "ambient", 5),
        DisplayMode("sports", "sports", 5),
        DisplayMode("stocks", "stocks", 5),
        DisplayMode("pomodoro", "pomodoro", 5),
        DisplayMode("clock", "clock", 5),
        DisplayMode("clock_widget", "clock", 5),
    )
)
