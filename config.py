# --- HARDWARE ---
MATRIX_WIDTH = 64
MATRIX_HEIGHT = 32
MATRIX_SLOWDOWN = 4
MATRIX_BRIGHTNESS = 100
MATRIX_MAPPING = 'adafruit-hat' 
MATRIX_PWM_BITS = 3
MATRIX_PWM_BITS_METRO = 3
MATRIX_PWM_BITS_FLIGHT = 3
MATRIX_PWM_BITS_WEATHER = 5
MATRIX_PWM_BITS_AMBIENT = 5
MATRIX_PWM_BITS_SPORTS = 5

# --- FONTS ---
FONT_PATH_TALL = "assets/fonts/6x10.bdf" 
FONT_PATH_SMALL = "assets/fonts/4x6.bdf"

# --- WMATA (DC Metro) ---
WMATA_API_KEY = ""
WMATA_STATION_CODE = "E05" 
STATION_SHORT_NAMES = {
    "Greenbelt": "Grnblt",
    "Huntington": "Huntgtn",
    "Columbia Heights": "ColHgts",
    "Georgia Ave-Petworth": "Ga Ave",
    "U Street": "U St",
    "Mt Vernon Sq": "MtVern",
    "Branch Av": "BranchAv", 
    "Fort Totten": "FtTottn",
    "No Passenger": "NoPsngr"
}

# --- WEATHER ---
OPENWEATHER_API_KEY = "" 
OPENWEATHER_CITY_ID = "4140963" # Washington DC
WEATHER_UNITS = "metric"

AMBIENT_SCENE_DURATION = 60  # seconds per scene

# Flight Tracking Configuration
AVIATIONSTACK_API_KEY = ""
FLIGHT_NUMBER = "AC57"  # Default flight to track
FLIGHT_UPDATE_INTERVAL = 1800

# --- SPORTS ---
SPORTS_VIEW_MODE = "all_live"   # "all_live" or "favorites"
SPORTS_FAVORITE_TEAMS = ""      # CSV of NBA abbreviations, e.g. "LAL,BOS"
SPORTS_TEST_DATE = ""           # YYYYMMDD to pin a date for testing; empty = today

# --- COLORS ---
COLOR_WHITE = (255, 255, 255)
COLOR_GREY = (100, 100, 100)
COLOR_BLUE = (0, 0, 255)
COLOR_YELLOW = (255, 255, 0)

LINE_COLORS = {
    "GR": (0, 255, 0),
    "YL": (255, 255, 0),
    "RD": (255, 0, 0),
    "BL": (0, 0, 255),
    "OR": (255, 165, 0),
    "SV": (220, 220, 220)
}

DISPLAY_MODE = "metro"
WEB_SERVER_PORT = 80
SETUP_MODE = False
