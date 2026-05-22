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
MATRIX_PWM_BITS_STOCKS = 5
MATRIX_PWM_BITS_CLOCK = 5
MATRIX_PWM_BITS_POMODORO = 5

# --- FONTS ---
FONT_PATH_TALL = "assets/fonts/6x10.bdf"
FONT_PATH_SMALL = "assets/fonts/4x6.bdf"

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
STOCKS_TICKER_SPEED = 25  # ticker scroll speed in pixels/sec

# --- POMODORO ---
POMODORO_FOCUS_MINUTES = 25
POMODORO_SHORT_BREAK_MINUTES = 5
POMODORO_LONG_BREAK_MINUTES = 15
POMODORO_LONG_BREAK_EVERY = 4
POMODORO_AUTO_START_BREAKS = True
POMODORO_AUTO_START_FOCUS = False

# --- CLOCK ---
# Font style options:
#   matrix
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
    "POMODORO_FOCUS_MINUTES",
    "POMODORO_SHORT_BREAK_MINUTES",
    "POMODORO_LONG_BREAK_MINUTES",
    "POMODORO_LONG_BREAK_EVERY",
    "POMODORO_AUTO_START_BREAKS",
    "POMODORO_AUTO_START_FOCUS",
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
