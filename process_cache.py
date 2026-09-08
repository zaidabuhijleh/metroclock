"""Process-lifetime caches that must survive ``importlib.reload(config)``.

``config`` is reloaded constantly at runtime to pick up runtime-editable
settings, and reloading re-executes the module top to bottom — which resets any
cache defined there. Anything expensive enough that recomputing it once per
reload would be a problem lives here instead, because this module is imported
normally and never reloaded.
"""

_CACHE: dict = {}


def get(key):
    return _CACHE.get(key)


def set(key, value):  # noqa: A001 - deliberate dict-like API
    _CACHE[key] = value
    return value


def clear(key=None):
    """Drop one entry, or everything when no key is given."""
    if key is None:
        _CACHE.clear()
    else:
        _CACHE.pop(key, None)
