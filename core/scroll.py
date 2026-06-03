"""Shared scroll-speed helper.

Per-frame integer pixel advancement is what makes LED-matrix scrolling look
smooth. To slow things down we still want a perfectly periodic pattern, so we
advance 1 pixel every N frames (the "stride") rather than introducing sub-pixel
accumulation that would alias against the frame clock.

A widget can pass its name to ``frame_stride`` to honor a per-widget override
(e.g. ``SCROLL_SPEED_STOCKS``); otherwise the global ``SCROLL_SPEED`` is used.
"""

import config


_PRESETS = {
    "slow": 3,    # ~17 px/s at 50fps
    "medium": 2,  # ~25 px/s at 50fps
    "fast": 1,    # ~50 px/s at 50fps
}


def frame_stride(widget: str | None = None) -> int:
    val = None
    if widget:
        val = getattr(config, f"SCROLL_SPEED_{widget.upper()}", None)
    if val is None or str(val).strip() == "":
        val = getattr(config, "SCROLL_SPEED", "fast")
    key = str(val or "fast").lower()
    return _PRESETS.get(key, 1)
