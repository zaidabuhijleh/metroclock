import time
import sys
import requests
import math

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
API_KEY = "c53cb0be42a44223bd50e608d5428b03"
STATION_CODE = "A01"

# MAPPING: Long Name -> Short Name (Must be 6-7 chars to fit with 'ARR')
SHORT_NAMES = {
    "Greenbelt":        "Grnblt",
    "Huntington":       "Huntgtn",
    "Columbia Heights": "ColHgts",
    "Georgia Ave-Petworth": "Ga Ave",
    "U Street":         "U St",
    "Mt Vernon Sq":     "MtVern",
    
    # CHANGE THIS LINE:
    # "BranchAv" (No space) -> Tight gap (looks like 1-pixel space)
    # "Branch Av" (Space)   -> Huge gap (looks like 4-pixel space)
    "Branch Av":       "BranchAv", 
    
    "Fort Totten":      "FtTottn",
    "No Passenger":     "NoPsngr"
}

# FONTS
# Make sure these are in the same folder!
FONT_THIN = "4x6.bdf"  # For Station Name & Line Code
FONT_BOLD = "5x8.bdf"  # For The Time

# COLORS
WHITE = (255, 255, 255)
GREY  = (180, 180, 180)
RED   = (255, 50, 0)
BLACK = (0, 0, 0)

LINE_COLORS = {
    "GR": (0, 255, 0),      "YL": (255, 255, 0),
    "RD": (255, 0, 0),      "BL": (0, 0, 255),
    "OR": (255, 165, 0),    "SV": (220, 220, 220)
}

# ---------------------------------------------------------
# SETUP
# ---------------------------------------------------------
try:
    from rgbmatrix import graphics, RGBMatrix, RGBMatrixOptions
except ImportError:
    from RGBMatrixEmulator import graphics, RGBMatrix, RGBMatrixOptions

def draw_filled_circle(canvas, x, y, r, color):
    # Simple raster circle algorithm
    for yi in range(-r, r + 1):
        width = int(math.sqrt(r*r - yi*yi))
        graphics.DrawLine(canvas, x - width, y + yi, x + width, y + yi, color)

def get_metro_data():
    headers = {'api_key': API_KEY}
    
    try:
        url = f"https://api.wmata.com/StationPrediction.svc/json/GetPrediction/{STATION_CODE}"
        resp = requests.get(url, headers=headers, timeout=5)
        data = resp.json()
        
        if 'Trains' in data:
            valid_trains = []
            for t in data['Trains']:
                line = t.get('Line', '--').strip()
                dest = t.get('Destination', '').strip()
                
                # UNIVERSAL FILTER 1: Bad Line Codes
                # Filter if line is empty, just dashes, or None
                if not line or line == "--":
                    continue

                # UNIVERSAL FILTER 2: Bad Destinations
                # Filter "No Passenger", "Train" (often used for maintenance), or empty text
                if dest in ["No Passenger", "Train", ""] or "ssenge" in dest:
                    continue

                valid_trains.append(t)
                
            return valid_trains
    except Exception as e:
        # Optional: print(f"API Error: {e}")
        pass
    return []
# ---------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------
def run():
# ---------------------------------------------------------
    # HARDWARE CONFIGURATION (Matches your working Demo)
    # ---------------------------------------------------------
    options = RGBMatrixOptions()
    options.rows = 32
    options.cols = 64
    options.chain_length = 1
    options.parallel = 1
    options.hardware_mapping = 'adafruit-hat'  # The bonnet
    
    # THE CRITICAL FIXES:
    options.gpio_slowdown = 4          # Fixes Pi Zero 2 speed issues
    options.disable_hardware_pulsing = True  # Fixes Pin 4/Sound conflict
    options.panel_type = "FM6126A"     # Fixes the "Garbage Lines"
    options.brightness = 50            # Safe brightness for indoor use
    
    options.drop_privileges = False
    
    matrix = RGBMatrix(options=options)
    canvas = matrix.CreateFrameCanvas()
    
    # Load Fonts
    font_thin = graphics.Font()
    font_thin.LoadFont(FONT_THIN)
    font_bold = graphics.Font()
    font_bold.LoadFont(FONT_BOLD)

    # STATE
    last_fetch = 0
    trains = []
    
    scroll_index = 0
    last_scroll_time = time.time()
    SCROLL_DELAY = 4.0  # Faster scroll since we only change 1 line at a time

    print("Rolling Clock Running...")

    while True:
        now = time.time()
        
        # 1. FETCH DATA
        if now - last_fetch > 30:
            new = get_metro_data()
            if new: trains = new
            last_fetch = now

        # 2. ROLLING LOGIC
        # If we have 3 or more trains, cycle through them
        if len(trains) > 2:
            if now - last_scroll_time > SCROLL_DELAY:
                scroll_index += 1
                # If we hit the end, loop back to start naturally
                if scroll_index >= len(trains):
                    scroll_index = 0
                last_scroll_time = now
        else:
            scroll_index = 0

        canvas.Clear()
        
        # 3. BUILD THE PAIR
        # We manually build the list of 2 trains to draw
        current_pair = []
        
        if len(trains) > 0:
            # TOP ROW: The current index
            current_pair.append(trains[scroll_index])
            
            # BOTTOM ROW: The NEXT index (wrapping around to 0 if needed)
            if len(trains) > 1:
                next_index = (scroll_index + 1) % len(trains)
                current_pair.append(trains[next_index])

        # 4. DRAW THE PAIR
        for i, train in enumerate(current_pair):
            y_base = i * 16 
            
            line = train['Line']
            dest = train['Destination']
            mins = train['Min']

            # -- NICKNAME CHECK --
            display_dest = SHORT_NAMES.get(dest, dest)

           # -- STEP B: DRAW ICONS --
            line_color = graphics.Color(*LINE_COLORS.get(line, (100,100,100)))
            draw_filled_circle(canvas, 8, 7 + y_base, 6, line_color)
            
            # CHANGE 1: Position moves to x=6 (Center of circle is 8, letter is ~4px wide)
            # CHANGE 2: 'line[0]' grabs just the first letter ("G" instead of "GR")
            graphics.DrawText(canvas, font_thin, 7, 10 + y_base, graphics.Color(*WHITE), line[0])

            # -- TRUNCATION LOGIC --
            if mins.isdigit():
                max_len = 7
                time_x = 53
                time_color = WHITE
            else:
                max_len = 6
                time_x = 48
                time_color = RED

            final_dest = display_dest[:max_len]

            # -- DRAW TEXT --
            graphics.DrawText(canvas, font_thin, 17, 10 + y_base, graphics.Color(*GREY), final_dest)
            graphics.DrawText(canvas, font_bold, time_x, 11 + y_base, graphics.Color(*time_color), mins)

        # Optional: Draw a tiny dot if there are more trains waiting
        if len(trains) > 2:
             canvas.SetPixel(63, 31, 0, 0, 255)

        canvas = matrix.SwapOnVSync(canvas)
        time.sleep(0.1)

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        sys.exit(0)