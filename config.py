import json
import os


# --- HARDWARE ---
MATRIX_WIDTH = 64
MATRIX_HEIGHT = 32
MATRIX_SLOWDOWN = 4
MATRIX_BRIGHTNESS = 100
MATRIX_MAPPING = "adafruit-hat"
MATRIX_PWM_BITS = 3
MATRIX_PWM_BITS_METRO = 3
MATRIX_PWM_BITS_FLIGHT = 3
MATRIX_PWM_BITS_WEATHER = 5
MATRIX_PWM_BITS_AMBIENT = 5
MATRIX_PWM_BITS_SPORTS = 5
MATRIX_PWM_BITS_STOCKS = 3
MATRIX_PWM_BITS_CLOCK = 5
# Clock+widget mode can run a lower bit depth for higher refresh and reduced shimmer.
MATRIX_PWM_BITS_CLOCK_WIDGET = 4
MATRIX_PWM_BITS_POMODORO = 5

# --- FONTS ---
FONT_PATH_TALL = "assets/fonts/6x10.bdf"
FONT_PATH_SMALL = "assets/fonts/4x6.bdf"
CLOCK_FONT_DIR = "assets/fonts/watchfaces"
CLOCK_BUILTIN_FONT_STYLES = (
    {"key": "matrix", "label": "Matrix", "type": "builtin"},
    {"key": "segment", "label": "Segment", "type": "builtin"},
)
CLOCK_FONT_FAMILIES = (
    {
        "key": "font_default",
        "label": "Default",
        "type": "font_family",
        "sizes": {
            "small": "default/4x6.bdf",
            "medium": "default/8x13.bdf",
            "large": {"path": "default/6x12.bdf", "scale": 2},
        },
    },
    {
        "key": "font_spleen",
        "label": "Spleen",
        "type": "font_family",
        "sizes": {
            "small": "spleen/5x8.bdf",
            "medium": "spleen/8x16.bdf",
            "large": "spleen/12x24.bdf",
        },
    },
)

# --- WMATA (DC Metro) ---
METRO_SYSTEM = "wmata"  # "wmata", "nyc", or "ttc"
WMATA_API_KEY = ""
WMATA_STATION_CODE = "E05"
WMATA_LINE_FILTER = ""  # CSV of line codes; empty = show all lines at station
STATION_SHORT_NAMES = {
    "Greenbelt": "Grnblt",
    "Huntington": "Huntgtn",
    "Columbia Heights": "ColHgts",
    "Georgia Ave-Petworth": "Ga Ave",
    "U Street": "U St",
    "Mt Vernon Sq": "MtVern",
    "Branch Av": "BranchAv",
    "Fort Totten": "FtTottn",
    "No Passenger": "NoPsngr",
}

# --- NYC Subway (MTA GTFS-RT) ---
# Feed docs: https://www.mta.info/developers
NYC_MTA_FEED_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs"
NYC_STOP_IDS = "127N,127S"  # CSV; example is Times Sq-42 St (1/2/3)
NYC_LINE_FILTER = ""  # CSV of line codes; empty = show all lines at station

# --- Toronto Subway (TTC / MyTTC) ---
TTC_STATION_ID = "queens_park_station"
TTC_STOP_URIS = "queens_park_station_subway_platform"  # CSV of platform stop URIs
TTC_LINE_FILTER = ""  # CSV of line codes (1,2,3,4); empty = show all lines

METRO_MIN_ARRIVAL_MINUTES = 0
METRO_MAX_ARRIVAL_MINUTES = 20
METRO_PAGE_TRANSITION = "slide"  # "slide" or "cut"

# --- WEATHER ---
OPENWEATHER_API_KEY = ""
OPENWEATHER_CITY_ID = "4140963"  # Washington DC
WEATHER_UNITS = "metric"

AMBIENT_SCENE_DURATION = 60  # seconds per scene
AMBIENT_SCENE = "auto"  # "auto" or pinned scene key

# Flight Tracking Configuration
AVIATIONSTACK_API_KEY = ""
FLIGHT_NUMBER = "AC57"  # Default flight to track
FLIGHT_UPDATE_INTERVAL = 1800

# --- SPORTS ---
SPORTS_VIEW_MODE = "all_live"  # "all_live" (all teams) or "favorites"
SPORTS_FAVORITE_TEAMS = ""  # CSV of NBA abbreviations, e.g. "LAL,BOS"
SPORTS_TEST_DATE = ""  # YYYYMMDD to pin a date for testing; empty = today
SPORTS_LIVE_FOCUS = True  # If True: when any chosen game is live, rotate only live games

# --- STOCKS ---
STOCKS_SYMBOLS = "AAPL,TSLA,NVDA,SPY"
STOCKS_VIEW_MODE = "ticker"
STOCKS_FOCUS_TIMEFRAME = "1D"
STOCKS_FOCUS_ROTATE_SECONDS = 8  # seconds per stock in focus view
STOCKS_TICKER_SPEED = 25  # legacy/unused — see SCROLL_SPEED

# --- SCROLL ---
# Global scroll speed for all marquee/ticker text. Restricted to values that
# produce uniform motion on the LED matrix (whole pixels per fixed frame stride).
#   "slow"   -> 1 px every 3 frames
#   "medium" -> 1 px every 2 frames
#   "fast"   -> 1 px every frame  (default)
SCROLL_SPEED = "fast"
# Per-widget overrides (leave as None or "" to inherit SCROLL_SPEED).
SCROLL_SPEED_STOCKS = None
SCROLL_SPEED_METRO = None
SCROLL_SPEED_SPORTS = None
SCROLL_SPEED_FLIGHT = None

# --- POMODORO ---
POMODORO_FOCUS_MINUTES = 25
POMODORO_SHORT_BREAK_MINUTES = 5
POMODORO_LONG_BREAK_MINUTES = 15
POMODORO_LONG_BREAK_EVERY = 4
POMODORO_AUTO_START_BREAKS = True
POMODORO_AUTO_START_FOCUS = False
# "mode_time" or "mode_time_task"
POMODORO_LAYOUT = "mode_time_task"
# Newline-delimited task queue; top line is shown first.
POMODORO_TODO_ITEMS = ""

# --- CLOCK ---
# Font style options:
#   matrix, segment, or a discovered font_* key from CLOCK_FONT_DIR
CLOCK_FONT_STYLE = "matrix"
# One sizing control for all styles.
CLOCK_SIZE = 1.0  # 0.5, 0.75, 1.0
CLOCK_COLOR_PRIMARY = ""  # Optional #RRGGBB override
CLOCK_COLOR_ACCENT = ""  # Optional #RRGGBB override
CLOCK_COLOR_ACCENT_2 = ""  # Optional #RRGGBB override
CLOCK_COLOR_DIM = ""  # Optional #RRGGBB override
CLOCK_COLOR_BG = ""  # Optional #RRGGBB override
CLOCK_SHOW_DATE = True
CLOCK_SHOW_AMPM = True
# "horizontal" -> clock top 2/3, widget bottom 1/3
# "vertical"   -> clock left 2/3, widget right 1/3
CLOCK_WIDGET_LAYOUT = "horizontal"
# Layout preset for clock+widget mode.
# "auto"                -> infer from CLOCK_WIDGET_LAYOUT + CLOCK_WIDGET_COUNT
# "horizontal_single"   -> top 6x2 clock + bottom 6x1 widget
# "horizontal_single_top" -> top 6x1 widget + bottom 6x2 clock
# "horizontal_split"    -> top 6x2 clock + two bottom mini widgets
# "vertical_focus"      -> left 3x3 clock + right 3x3 focus widget
# "vertical_split_focus"-> left 3x2 clock + left-bottom mini + right focus widget
# "vertical_split_focus_top" -> left-top mini + left 3x2 clock + right focus widget
CLOCK_WIDGET_PRESET = "auto"
# Widget shown in clock+widget mode.
CLOCK_WIDGET_SOURCE = "weather"
# 1 = clock + one widget pane, 2 = clock + two widget panes
CLOCK_WIDGET_COUNT = 1
# Secondary widget used when CLOCK_WIDGET_COUNT=2.
CLOCK_WIDGET_SOURCE_SECONDARY = "stocks"
# Legacy mini-widget text motion style fallback.
# "metro"  -> single-pass scroll with hold (like metro destination rows)
# "ticker" -> continuous wrap-around ticker scroll
CLOCK_WIDGET_SCROLL_MODE = "metro"
# Per-pane mini-widget text motion style.
CLOCK_WIDGET_SCROLL_MODE_PRIMARY = "metro"
CLOCK_WIDGET_SCROLL_MODE_SECONDARY = "metro"
# 24-hour vs 12-hour clock display.
CLOCK_USE_24H = False

# --- COLORS ---
COLOR_WHITE = (255, 255, 255)
COLOR_GREY = (100, 100, 100)
COLOR_BLUE = (0, 0, 255)
COLOR_YELLOW = (255, 255, 0)

DISPLAY_MODE = "clock"
WEB_SERVER_PORT = 80
SETUP_MODE = False


# Runtime/user-editable keys. Defaults live above; persistent overrides live in
# a local JSON file; environment variables may override both.
RUNTIME_EDITABLE_FIELDS = {
    "METRO_SYSTEM",
    "WMATA_API_KEY",
    "WMATA_STATION_CODE",
    "WMATA_LINE_FILTER",
    "NYC_MTA_FEED_URL",
    "NYC_STOP_IDS",
    "NYC_LINE_FILTER",
    "TTC_STATION_ID",
    "TTC_STOP_URIS",
    "TTC_LINE_FILTER",
    "METRO_MIN_ARRIVAL_MINUTES",
    "METRO_MAX_ARRIVAL_MINUTES",
    "METRO_PAGE_TRANSITION",
    "OPENWEATHER_API_KEY",
    "OPENWEATHER_CITY_ID",
    "WEATHER_UNITS",
    "AVIATIONSTACK_API_KEY",
    "FLIGHT_NUMBER",
    "DISPLAY_MODE",
    "MATRIX_BRIGHTNESS",
    "MATRIX_PWM_BITS_CLOCK_WIDGET",
    "WEB_SERVER_PORT",
    "SETUP_MODE",
    "SPORTS_VIEW_MODE",
    "SPORTS_FAVORITE_TEAMS",
    "SPORTS_TEST_DATE",
    "SPORTS_LIVE_FOCUS",
    "AMBIENT_SCENE",
    "STOCKS_SYMBOLS",
    "STOCKS_VIEW_MODE",
    "STOCKS_FOCUS_TIMEFRAME",
    "STOCKS_FOCUS_ROTATE_SECONDS",
    "STOCKS_TICKER_SPEED",
    "SCROLL_SPEED",
    "SCROLL_SPEED_STOCKS",
    "SCROLL_SPEED_METRO",
    "SCROLL_SPEED_SPORTS",
    "SCROLL_SPEED_FLIGHT",
    "POMODORO_FOCUS_MINUTES",
    "POMODORO_SHORT_BREAK_MINUTES",
    "POMODORO_LONG_BREAK_MINUTES",
    "POMODORO_LONG_BREAK_EVERY",
    "POMODORO_AUTO_START_BREAKS",
    "POMODORO_AUTO_START_FOCUS",
    "POMODORO_LAYOUT",
    "POMODORO_TODO_ITEMS",
    "CLOCK_FONT_STYLE",
    "CLOCK_SIZE",
    "CLOCK_COLOR_PRIMARY",
    "CLOCK_COLOR_ACCENT",
    "CLOCK_COLOR_ACCENT_2",
    "CLOCK_COLOR_DIM",
    "CLOCK_COLOR_BG",
    "CLOCK_SHOW_DATE",
    "CLOCK_SHOW_AMPM",
    "CLOCK_WIDGET_LAYOUT",
    "CLOCK_WIDGET_PRESET",
    "CLOCK_WIDGET_SOURCE",
    "CLOCK_WIDGET_COUNT",
    "CLOCK_WIDGET_SOURCE_SECONDARY",
    "CLOCK_WIDGET_SCROLL_MODE",
    "CLOCK_WIDGET_SCROLL_MODE_PRIMARY",
    "CLOCK_WIDGET_SCROLL_MODE_SECONDARY",
    "CLOCK_USE_24H",
}

def _default_runtime_config_path():
    explicit = os.environ.get("METROCLOCK_CONFIG_PATH")
    if explicit:
        return explicit

    try:
        is_root = os.geteuid() == 0
    except AttributeError:
        is_root = False

    if is_root:
        return "/etc/metroclock/config.json"
    return os.path.join(os.path.expanduser("~"), ".config", "metroclock", "config.json")


RUNTIME_CONFIG_PATH = _default_runtime_config_path()


def get_runtime_config_path() -> str:
    return RUNTIME_CONFIG_PATH


def _clock_font_root():
    if os.path.isabs(CLOCK_FONT_DIR):
        return CLOCK_FONT_DIR
    return os.path.join(os.path.dirname(__file__), CLOCK_FONT_DIR)


def get_clock_font_faces():
    faces = [dict(face) for face in CLOCK_BUILTIN_FONT_STYLES]
    root = _clock_font_root()
    for family in CLOCK_FONT_FAMILIES:
        sizes = {}
        available = False
        for size_key, spec in family["sizes"].items():
            if isinstance(spec, dict):
                rel_path = spec.get("path", "")
                scale = spec.get("scale", 1)
            else:
                rel_path = spec
                scale = 1
            path = os.path.join(root, rel_path)
            sizes[size_key] = {
                "path": path,
                "scale": scale,
            }
            available = available or os.path.isfile(path)
        if available:
            face = dict(family)
            face["sizes"] = sizes
            faces.append(face)
    return faces


def get_clock_font_style_options():
    return tuple(face["key"] for face in get_clock_font_faces())


def get_clock_font_face(style):
    style = str(style or "").strip().lower()
    legacy_family_map = {
        "font_4x6": "font_default",
        "font_8x13": "font_default",
        "font_10x20": "font_default",
        "font_spleen_5x8": "font_spleen",
        "font_spleen_8x16": "font_spleen",
        "font_spleen_12x24": "font_spleen",
    }
    style = legacy_family_map.get(style, style)
    for face in get_clock_font_faces():
        if face["key"] == style:
            return face
    return None


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
    raise ValueError("invalid bool value")


def _coerce_value(raw, current):
    if raw is None:
        return current
    if isinstance(current, bool):
        try:
            return _parse_bool(raw)
        except ValueError:
            return current
    if isinstance(current, int):
        try:
            return int(raw)
        except Exception:
            return current
    if isinstance(current, float):
        try:
            return float(raw)
        except Exception:
            return current
    if isinstance(current, str):
        return str(raw)
    return raw


def _load_runtime_overrides(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _apply_runtime_overrides():
    file_overrides = _load_runtime_overrides(RUNTIME_CONFIG_PATH)
    # Backward compatibility: migrate legacy clock size key.
    if "CLOCK_SIZE" not in file_overrides and "CLOCK_SIZE_SCALE" in file_overrides:
        file_overrides["CLOCK_SIZE"] = file_overrides["CLOCK_SIZE_SCALE"]
    if "CLOCK_WIDGET_SCROLL_MODE_PRIMARY" not in file_overrides and "CLOCK_WIDGET_SCROLL_MODE" in file_overrides:
        file_overrides["CLOCK_WIDGET_SCROLL_MODE_PRIMARY"] = file_overrides["CLOCK_WIDGET_SCROLL_MODE"]
    if "CLOCK_WIDGET_SCROLL_MODE_SECONDARY" not in file_overrides and "CLOCK_WIDGET_SCROLL_MODE" in file_overrides:
        file_overrides["CLOCK_WIDGET_SCROLL_MODE_SECONDARY"] = file_overrides["CLOCK_WIDGET_SCROLL_MODE"]

    for key in RUNTIME_EDITABLE_FIELDS:
        if key not in file_overrides or key not in globals():
            continue
        globals()[key] = _coerce_value(file_overrides[key], globals()[key])

    for key in RUNTIME_EDITABLE_FIELDS:
        if key not in globals():
            continue
        env_val = None
        prefixed_name = f"METROCLOCK_{key}"
        if prefixed_name in os.environ:
            env_val = os.environ[prefixed_name]
        elif key in os.environ:
            env_val = os.environ[key]
        if env_val is not None:
            globals()[key] = _coerce_value(env_val, globals()[key])


_apply_runtime_overrides()
