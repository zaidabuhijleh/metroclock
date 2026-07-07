"""Shared scroll-speed helper.

Per-frame pixel advancement is what makes LED-matrix scrolling look smooth.
Whole-number strides are the cleanest, but the "relaxed" preset intentionally
sits between fast and medium for widgets that need only a small slowdown.

A widget can pass its name to ``frame_stride`` to honor a per-widget override
(e.g. ``SCROLL_SPEED_STOCKS``); otherwise the global ``SCROLL_SPEED`` is used.
"""

import config


_PRESETS = {
    "slow": 3,    # ~17 px/s at 50fps
    "medium": 2,  # ~25 px/s at 50fps
    "relaxed": 1.35,  # ~37 px/s at 50fps
    "fast": 1,    # ~50 px/s at 50fps
}


def frame_stride(widget: str | None = None) -> float:
    val = None
    if widget:
        val = getattr(config, f"SCROLL_SPEED_{widget.upper()}", None)
    if val is None or str(val).strip() == "":
        val = getattr(config, "SCROLL_SPEED", "fast")
    key = str(val or "fast").lower()
    return max(1.0, float(_PRESETS.get(key, 1)))
