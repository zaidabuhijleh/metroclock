import time
import requests
from PIL import Image, ImageDraw, ImageFont
from core.widget import Widget
import config

# --- PIXEL PERFECT LETTER MAPS ---
# 1 = Pixel On, 0 = Pixel Off
# These are 3x5 bitmaps (Compact and sharp)
BITMAP_LETTERS = {
    'R': [(0,0), (1,0), (2,0), (0,1), (2,1), (0,2), (1,2), (0,3), (2,3), (0,4), (2,4)],
    'B': [(0,0), (1,0), (0,1), (2,1), (0,2), (1,2), (0,3), (2,3), (0,4), (1,4)],
    'O': [(1,0), (0,1), (2,1), (0,2), (2,2), (0,3), (2,3), (1,4)],
    'S': [(1,0), (2,0), (0,1), (1,2), (2,3), (0,4), (1,4)],
    'G': [(1,0), (2,0), (0,1), (0,2), (2,2), (0,3), (2,3), (1,4), (2,4)],
    'Y': [(0,0), (2,0), (0,1), (2,1), (1,2), (1,3), (1,4)],
    # Fallback
    'L': [(0,0), (0,1), (0,2), (0,3), (0,4), (1,4), (2,4)] 
}

class MetroWidget(Widget):
    def __init__(self, width, height):
        super().__init__(width, height)
        self.trains = []
        self.scroll_index = 0
        self.last_fetch = 0
        
        # Animation State
        self.page_start_time = time.time()
        self.scroll_speed = 20
        
        # Load Fonts
        try:
            self.font_tall = ImageFont.truetype(config.FONT_PATH_TALL, 10)
        except:
            self.font_tall = ImageFont.load_default()

    def update(self):
        """Fetch API Data"""
        now = time.time()
        if now - self.last_fetch > 30: 
            headers = {'api_key': config.WMATA_API_KEY}
            try:
                url = f"https://api.wmata.com/StationPrediction.svc/json/GetPrediction/{config.WMATA_STATION_CODE}"
                resp = requests.get(url, headers=headers, timeout=5)
                data = resp.json()
                
                if 'Trains' in data:
                    valid = []
                    for t in data['Trains']:
                        line = t.get('Line', '--').strip()
                        dest = t.get('Destination', '').strip()
                        if not line or line == "--": continue
                        if dest in ["No Passenger", "Train", ""] or "ssenge" in dest: continue
                        valid.append(t)
                    self.trains = valid
                self.last_fetch = now
            except Exception as e:
                print(f"API Error: {e}")

    def draw(self):
        draw = ImageDraw.Draw(self.canvas)
        draw.rectangle((0,0, self.width, self.height), fill=(0,0,0))

        if not self.trains:
            return self.canvas

        # --- 1. DETERMINE WHICH TRAINS TO SHOW ---
        t1 = self.trains[self.scroll_index]
        t2 = self.trains[(self.scroll_index + 1) % len(self.trains)] if len(self.trains) > 1 else None
        
        current_pair = [t1]
        if t2: current_pair.append(t2)

        # --- 2. CALCULATE PAGE DURATION ---
        longest_scroll_time = 0
        
        # CHANGED: Adjusted start position to 13 (since mask is smaller)
        TEXT_START_X = 13 
        
        for train in current_pair:
            eta_width = self.font_tall.getlength(train['Min'])
            visible_width = (64 - eta_width - 3) - TEXT_START_X 
            dest = train['Destination']
            text_width = self.font_tall.getlength(dest)

            if text_width > visible_width:
                # Snap to last word logic
                last_space = dest.rfind(' ')
                if last_space != -1:
                    prefix_width = self.font_tall.getlength(dest[:last_space + 1])
                    scroll_dist = prefix_width
                else:
                    scroll_dist = text_width - visible_width
                
                time_needed = scroll_dist / self.scroll_speed
                if time_needed > longest_scroll_time:
                    longest_scroll_time = time_needed

        page_duration = max(4.0, 1.0 + longest_scroll_time + 2.0)

        # --- 3. HANDLE CYCLING ---
        now = time.time()
        time_on_page = now - self.page_start_time

        if time_on_page > page_duration:
            if len(self.trains) > 2:
                self.scroll_index = (self.scroll_index + 1) % len(self.trains)
            self.page_start_time = now
            time_on_page = 0 

        # --- 4. DRAW ROWS ---
        for i, train in enumerate(current_pair):
            row_y = i * 16
            line = train['Line']
            dest = train['Destination']
            mins = train['Min']
            line_color = config.LINE_COLORS.get(line, config.COLOR_GREY)

            # --- A. DYNAMIC MASK CALCULATION ---
            eta_width = self.font_tall.getlength(mins)
            mask_x_start = 64 - eta_width - 3
            
            # Recalculate space based on new TEXT_START_X
            visible_space = mask_x_start - TEXT_START_X

            # --- B. SCROLLING TEXT ---
            text_width = self.font_tall.getlength(dest)
            x_pos = TEXT_START_X
            
            if text_width > visible_space:
                last_space = dest.rfind(' ')
                if last_space != -1:
                    max_offset = self.font_tall.getlength(dest[:last_space + 1])
                else:
                    max_offset = text_width - visible_space

                if time_on_page < 1.0:
                    offset = 0
                else:
                    active_scroll_time = time_on_page - 1.0
                    offset = active_scroll_time * self.scroll_speed
                    if offset > max_offset: 
                        offset = max_offset
                
                x_pos = TEXT_START_X - offset
            
            draw.text((x_pos, row_y + 3), dest, font=self.font_tall, fill=config.COLOR_BLUE)

            # --- C. MASKS ---
            # CHANGED: Left Mask is now smaller (0 to 12) to fit tighter to the icon
            draw.rectangle((0, row_y, 12, row_y + 16), fill=(0,0,0)) 
            draw.rectangle((mask_x_start, row_y, 64, row_y + 16), fill=(0,0,0)) # Right

            # --- D. ICONS & TIME ---
            # CHANGED: Octagon shifted right to x=2
            self._draw_octagon(draw, 2, row_y + 3, line_color, line[0])

            # Time (Right)
            time_x = 64 - eta_width - 1
            draw.text((time_x, row_y + 3), mins, font=self.font_tall, fill=config.COLOR_WHITE)

        return self.canvas

    def _draw_octagon(self, draw, x, y, color, text):
        """Draws a 9x9 Octagon with Pixel-Perfect Letter"""
        points = [
            (x + 2, y), (x + 6, y),          
            (x + 8, y + 2), (x + 8, y + 6),  
            (x + 6, y + 8), (x + 2, y + 8),  
            (x, y + 6), (x, y + 2)           
        ]
        draw.polygon(points, outline=color, fill=color)
        
        letter_pixels = BITMAP_LETTERS.get(text, [])
        # Center 3x5 letter in 9x9 box
        start_x = x + 3
        start_y = y + 2
        for (px, py) in letter_pixels:
            draw.point((start_x + px, start_y + py), fill=(255, 255, 255))