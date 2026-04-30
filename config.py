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
METRO_SYSTEM = "wmata"  # "wmata" or "nyc"
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
    "No Passenger": "NoPsngr"
}

# --- NYC Subway (MTA GTFS-RT) ---
# Feed docs: https://www.mta.info/developers
NYC_MTA_FEED_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs"
NYC_STOP_IDS = "127N,127S"  # CSV; example is Times Sq-42 St (1/2/3)
NYC_LINE_FILTER = ""  # CSV of line codes; empty = show all lines at station
METRO_MIN_ARRIVAL_MINUTES = 0
METRO_MAX_ARRIVAL_MINUTES = 20

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
SPORTS_VIEW_MODE = "all_live"   # "all_live" (all teams) or "favorites"
SPORTS_FAVORITE_TEAMS = ""      # CSV of NBA abbreviations, e.g. "LAL,BOS"
SPORTS_TEST_DATE = ""           # YYYYMMDD to pin a date for testing; empty = today
SPORTS_LIVE_FOCUS = True        # If True: when any chosen game is live, rotate only live games

# --- COLORS ---
COLOR_WHITE = (255, 255, 255)
COLOR_GREY = (100, 100, 100)
COLOR_BLUE = (0, 0, 255)
COLOR_YELLOW = (255, 255, 0)

DISPLAY_MODE = "metro"
WEB_SERVER_PORT = 80
SETUP_MODE = False
