import time
import sys
import requests
import math

try:
    from rgbmatrix import graphics, RGBMatrix, RGBMatrixOptions
except ImportError:
    from RGBMatrixEmulator import graphics, RGBMatrix, RGBMatrixOptions

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
API_KEY = "c53cb0be42a44223bd50e608d5428b03"
STATION_CODE = "A01"

# SHORT NAMES (Optimized for 64-width)
SHORT_NAMES = {
    "Greenbelt":        "Grnblt",
    "Huntington":       "Huntgtn",
    "Columbia Heights": "ColHgts",
    "Georgia Ave-Petworth": "Ga Ave",
    "U Street":         "U St",
    "Mt Vernon Sq":     "MtVern",
    "Branch Av":        "BranchAv", 
    "Fort Totten":      "FtTottn",
    "No Passenger":     "NoPsngr"
}

# --- FONTS ---
# You need a taller font to match the example. 
# 6x10.bdf or 6x12.bdf are best. 
# If you don't have them, use 5x8.bdf, but it won't be as tall.
FONT_TALL = "tall.bdf"    # Name/Dest (Try 6x10.bdf)
FONT_SMALL = "4x6.bdf"    # For the letter inside the circle

# COLORS
WHITE = (255, 255, 255)
GREY  = (100, 100, 100) # Dimmer grey for text looks more premium
BLUE  = (0, 0, 255)     # The example uses Blue text often
RED   = (255, 0, 0)

LINE_COLORS = {
    "GR": (0, 255, 0),      "YL": (255, 255, 0),
    "RD": (255, 0, 0),      "BL": (0, 0, 255),
    "OR": (255, 165, 0),    "SV": (220, 220, 220)
}

# ---------------------------------------------------------
# CUSTOM DRAWING FUNCTIONS
# ---------------------------------------------------------

def draw_subway_icon(canvas, x, y, color, text, font):
    """
    Draws a hand-crafted 'round' circle.
    Mathematical circles look like squares on low res. 
    This creates an 11x11 'octagon' that looks like a smooth circle.
    """
    c = color
    
    # Vertical Sides (Left and Right)
    graphics.DrawLine(canvas, x, y+3, x, y+7, c)      # Left
    graphics.DrawLine(canvas, x+10, y+3, x+10, y+7, c) # Right
    
    # Horizontal Sides (Top and Bottom)
    graphics.DrawLine(canvas, x+3, y, x+7, y, c)      # Top
    graphics.DrawLine(canvas, x+3, y+10, x+7, y+10, c) # Bottom

    # Corners (The pixels that make it round)
    # Top-Left
    canvas.SetPixel(x+1, y+2, c.red, c.green, c.blue)
    canvas.SetPixel(x+2, y+1, c.red, c.green, c.blue)
    # Top-Right
    canvas.SetPixel(x+8, y+1, c.red, c.green, c.blue)
    canvas.SetPixel(x+9, y+2, c.red, c.green, c.blue)
    # Bottom-Left
    canvas.SetPixel(x+1, y+8, c.red, c.green, c.blue)
    canvas.SetPixel(x+2, y+9, c.red, c.green, c.blue)
    # Bottom-Right
    canvas.SetPixel(x+8, y+9, c.red, c.green, c.blue)
    canvas.SetPixel(x+9, y+8, c.red, c.green, c.blue)

    # Draw the Line Letter inside
    # Center is roughly x+3, y+2 for a small font
    graphics.DrawText(canvas, font, x+4, y+8, graphics.Color(255,255,255), text)


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
                if not line or line == "--": continue
                if dest in ["No Passenger", "Train", ""] or "ssenge" in dest: continue
                valid_trains.append(t)
            return valid_trains
    except:
        pass
    return []

# ---------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------
def run():
    options = RGBMatrixOptions()
    options.rows = 32
    options.cols = 64
    options.chain_length = 1
    options.parallel = 1
    options.hardware_mapping = 'adafruit-hat'
    options.gpio_slowdown = 4
    options.disable_hardware_pulsing = True
    options.panel_type = "FM6126A"
    options.brightness = 60 # Slightly brighter for the "neon" look
    options.drop_privileges = False
    
    matrix = RGBMatrix(options=options)
    canvas = matrix.CreateFrameCanvas()
    
    # LOAD FONTS
    font_tall = graphics.Font()
    try:
        font_tall.LoadFont(FONT_TALL)
    except:
        print(f"Could not load {FONT_TALL}, using default")
        font_tall.LoadFont("5x8.bdf") # Fallback

    font_small = graphics.Font()
    font_small.LoadFont(FONT_SMALL)

    last_fetch = 0
    trains = []
    scroll_index = 0
    last_scroll_time = time.time()
    SCROLL_DELAY = 4.0 

    print("Subway Clock Running...")

    while True:
        now = time.time()
        
        # 1. FETCH DATA
        if now - last_fetch > 30:
            new = get_metro_data()
            if new: trains = new
            last_fetch = now

        # 2. SCROLL LOGIC
        if len(trains) > 2:
            if now - last_scroll_time > SCROLL_DELAY:
                scroll_index = (scroll_index + 1) % len(trains)
                last_scroll_time = now
        else:
            scroll_index = 0

        canvas.Clear()
        
        # 3. BUILD PAIR
        current_pair = []
        if len(trains) > 0:
            current_pair.append(trains[scroll_index])
            if len(trains) > 1:
                next_index = (scroll_index + 1) % len(trains)
                current_pair.append(trains[next_index])

        # 4. DRAW THE PAIR (TIGHT LAYOUT)
        # We use explicit Y coordinates to get that tight spacing
        
        for i, train in enumerate(current_pair):
            # Row 1 starts at Y=0, Row 2 starts at Y=16
            row_y = i * 16 
            
            line = train['Line']
            dest = train['Destination']
            mins = train['Min']
            
            # --- DRAW ICON ---
            # Using custom hollow circle drawer
            # Y=2 pushes it slightly down from top edge for centering
            line_c = LINE_COLORS.get(line, (100,100,100))
            col_obj = graphics.Color(*line_c)
            
            draw_subway_icon(canvas, 1, row_y + 2, col_obj, line[0], font_small)

            # --- DRAW TEXT ---
            # Font Baseline: For a 10px tall font, baseline is near +9 or +10
            text_baseline = row_y + 11 

            display_dest = SHORT_NAMES.get(dest, dest)
            max_len = 7 if mins.isdigit() else 6
            final_dest = display_dest[:max_len]

            # Draw Destination (Blue/Grey to match style)
            # X=15 gives padding after the icon
            graphics.DrawText(canvas, font_tall, 15, text_baseline, graphics.Color(0, 0, 255), final_dest)

            # --- DRAW TIME ---
            # Align to the right
            time_x = 52
            if not mins.isdigit(): time_x = 48 # Move "ARR" or "BRD" left
            
            graphics.DrawText(canvas, font_tall, time_x, text_baseline, graphics.Color(*WHITE), mins)

        canvas = matrix.SwapOnVSync(canvas)
        time.sleep(0.05)

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        sys.exit(0)