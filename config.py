# MetroClock/config.py

# --- HARDWARE ---
MATRIX_WIDTH = 64
MATRIX_HEIGHT = 32
MATRIX_SLOWDOWN = 4
MATRIX_BRIGHTNESS = 30
MATRIX_MAPPING = 'adafruit-hat' 

# --- FONTS ---
FONT_PATH_TALL = "assets/fonts/6x10.bdf" 
FONT_PATH_SMALL = "assets/fonts/4x6.bdf"

# --- WMATA (DC Metro) ---
WMATA_API_KEY = "c53cb0be42a44223bd50e608d5428b03"
WMATA_STATION_CODE = "E05" # Metro Center

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
OPENWEATHER_API_KEY = "d5092fab79001316a8ce418977440796" 
OPENWEATHER_CITY_ID = "4140963" # Washington DC
WEATHER_UNITS = "metric"

# Flight Tracking Configuration
AVIATIONSTACK_API_KEY = "056c570bf590bae3e6abf270b769d214"
FLIGHT_NUMBER = "AC57"  # Default flight to track
FLIGHT_UPDATE_INTERVAL = 1800

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