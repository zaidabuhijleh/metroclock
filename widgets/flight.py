import time
import re
from datetime import datetime
import requests
from PIL import Image, ImageDraw, ImageFont
from core.widget import Widget
import config
import widgets.icons as icons

class FlightWidget(Widget):
    def __init__(self, width, height):
        super().__init__(width, height)
        self.data = None
        self.status_text = "INITIALIZING"
        self.next_fetch_time = 0
        
        self.COLOR_GOLD = (255, 180, 0)
        self.COLOR_PURPLE = (180, 80, 255)
        self.COLOR_WHITE = (255, 255, 255)
        self.COLOR_GREY = (150, 150, 150)

        try:
            self.font = ImageFont.truetype(config.FONT_PATH_TALL, 10)
        except:
            self.font = ImageFont.load_default()

    def _parse_api_time(self, time_str):
        if not time_str: return None
        try:
            return datetime.fromisoformat(time_str.replace('Z', '+00:00')).timestamp()
        except: return None

    def update(self):
        now = time.time()
        if self.data is None or now >= self.next_fetch_time:
            self._fetch_flight_data()

    def _fetch_flight_data(self):
        try:
            params = {'access_key': config.AVIATIONSTACK_API_KEY, 'flight_iata': config.FLIGHT_NUMBER}
            resp = requests.get("http://api.aviationstack.com/v1/flights", params=params, timeout=10)
            if resp.status_code == 200:
                res_json = resp.json()
                print("JSON: "+ res_json)
                if res_json.get('data') and len(res_json['data']) > 0:
                    self.data = res_json['data'][0]
                    self.status_text = None
                    self._schedule_next_check()
                else:
                    self.status_text = "NOT FOUND"
                    self.next_fetch_time = time.time() + 600 
            else:
                self.status_text = f"ERR {resp.status_code}"
                self.next_fetch_time = time.time() + 300
        except:
            self.status_text = "CONN ERR"
            self.next_fetch_time = time.time() + 300

    def _schedule_next_check(self):
        status = self.data['flight_status']
        now = time.time()
        if status in ['scheduled', 'delayed']:
            t_str = self.data['departure'].get('estimated') or self.data['departure'].get('scheduled')
            takeoff_ts = self._parse_api_time(t_str)
            self.next_fetch_time = (takeoff_ts or now) + 300 
        elif status == 'active':
            l_str = self.data['arrival'].get('estimated') or self.data['arrival'].get('scheduled')
            landing_ts = self._parse_api_time(l_str)
            self.next_fetch_time = (landing_ts or now) + 300 
        else:
            self.next_fetch_time = now + 43200

    def _get_live_progress(self):
        """Fixed math to prioritize estimated arrival for accurate tracking."""
        if not self.data: return 0.05
        status = self.data['flight_status']
        if status == 'landed': return 1.0
        if status != 'active': return 0.05
        
        # Priority on ESTIMATED for arrival to keep the plane position accurate
        dep = self._parse_api_time(self.data['departure'].get('scheduled'))
        arr = self._parse_api_time(self.data['arrival'].get('estimated') or self.data['arrival'].get('scheduled'))
        
        if not dep or not arr: return 0.5
        
        now = time.time()
        duration = arr - dep
        if duration <= 0: return 0.5
        
        progress = (now - dep) / duration
        return max(0.05, min(0.98, progress)) # Clamp at 98% until landed

    def draw_scrolling_status(self, draw, text, x_range, y, color):
        x_min, x_max = x_range
        width_limit = x_max - x_min
        bbox = draw.textbbox((0, 0), text, font=self.font)
        text_width = bbox[2] - bbox[0]
        
        if text_width <= width_limit:
            draw.text((x_min, y), text, font=self.font, fill=color)
        else:
            full_path = text_width + 15
            scroll_pos = int(time.time() * 8) % (full_path + 30)
            offset = max(0, scroll_pos - 15)
            if offset > text_width - width_limit:
                offset = text_width - width_limit

            temp_txt = Image.new('RGB', (text_width, 16), (0,0,0))
            temp_draw = ImageDraw.Draw(temp_txt)
            temp_draw.text((0, 0), text, font=self.font, fill=color)
            self.canvas.paste(temp_txt.crop((offset, 0, offset + width_limit, 16)), (x_min, y))

    def draw_clean_time(self, draw, eta_str, x, y, color):
        """Draws time with a custom 1-pixel dot colon."""
        if ":" not in eta_str:
            draw.text((x, y), eta_str, font=self.font, fill=color)
            return
        hh, mm = eta_str.split(":")
        draw.text((x, y), hh, font=self.font, fill=color)
        bbox_hh = draw.textbbox((0, 0), hh, font=self.font)
        colon_x = x + (bbox_hh[2] - bbox_hh[0]) + 1
        draw.point((colon_x, y + 3), fill=color)
        draw.point((colon_x, y + 7), fill=color)
        draw.text((colon_x + 2, y), mm, font=self.font, fill=color)

    def draw_split_flight_no(self, draw, flight_no, x, y):
        """Standardizing vertical alignment to match Metro look."""
        bbox = draw.textbbox((0, 0), flight_no, font=self.font)
        if (bbox[2] - bbox[0]) <= 30:
            draw.text((x, y + 4), flight_no, font=self.font, fill=self.COLOR_GOLD)
        else:
            match = re.match(r"([A-Z]+)([0-9]+)", flight_no)
            if match:
                letters, numbers = match.groups()
                draw.text((x, y), letters, font=self.font, fill=self.COLOR_GOLD)
                draw.text((x, y + 10), numbers, font=self.font, fill=self.COLOR_GOLD)
            else:
                draw.text((x, y), flight_no[:3], font=self.font, fill=self.COLOR_GOLD)
                draw.text((x, y + 10), flight_no[3:], font=self.font, fill=self.COLOR_GOLD)

    def draw(self):
        draw = ImageDraw.Draw(self.canvas)
        draw.rectangle((0, 0, self.width, self.height), fill=(0, 0, 0))

        if not self.data:
            draw.text((2, 10), self.status_text, font=self.font, fill=self.COLOR_GREY)
            return self.canvas

        # --- DYNAMIC LAYOUT & STATUS COLORS ---
        flight_no = self.data['flight']['iata']
        raw_status = self.data.get('flight_status', '').lower()
        # raw_status = "delayed"
        # print("Status: "+ raw_status)
        
        if raw_status == "active":
            status_line1, status_line2 = "EN", "ROUTE"
            status_color = self.COLOR_PURPLE
            bar_color = (0, 255, 0) 
        elif raw_status == "delayed":
            status_line1, status_line2 = "DE-", "LAYED"
            status_color = (255, 0, 0)
            bar_color = (255, 0, 0)
        elif raw_status == "landed":
            status_line1, status_line2 = "LAND-", "ED"
            status_color = (0, 255, 0)
            bar_color = (0, 255, 0)
        else:
            status_line1, status_line2 = raw_status.upper()[:5], ""
            status_color = self.COLOR_WHITE
            bar_color = self.COLOR_GREY

        match = re.match(r"([A-Z]+)([0-9]+)", flight_no)
        letters, numbers = match.groups() if match else (flight_no[:2], flight_no[2:])
        bbox_l = draw.textbbox((0, 0), letters, font=self.font)
        split_x = (bbox_l[2] - bbox_l[0]) + 6

        draw.text((2, 0), letters, font=self.font, fill=self.COLOR_GOLD)
        draw.text((2, 10), numbers, font=self.font, fill=self.COLOR_GOLD)

        if int(time.time()) % 10 < 5:
            draw.text((split_x, 0), status_line1, font=self.font, fill=status_color)
            if status_line2: draw.text((split_x, 10), status_line2, font=self.font, fill=status_color)
        else:
            draw.text((split_x, 0), "ETA", font=self.font, fill=status_color)
            arr_str = self.data['arrival'].get('estimated') or self.data['arrival'].get('scheduled')
            eta = datetime.fromisoformat(arr_str.replace('Z', '+00:00')).strftime('%H:%M') if arr_str else "--:--"
            self.draw_clean_time(draw, eta, split_x, 10, status_color)

       # --- PROGRESS BAR (Guaranteed Full-Length Rail) ---
        bar_y = 26
        track_start, track_end = 6, 58 
        progress = self._get_live_progress()
        plane_x = int(track_start + (progress * (track_end - track_start)))

        # 1. DRAW THE FULL RAIL FIRST: This connects both circles permanently
        # Using a slightly brighter grey (60, 60, 60) so it's visible but not distracting.
        draw.line((track_start, bar_y, track_end, bar_y), fill=(60, 60, 60), width=1)

        # 2. DRAW THE GREEN PROGRESS: Only up to the plane's tail area
        # Stopping 14 pixels before the nose tip ensures no green bleeds into the plane icon.
        if plane_x > track_start + 14:
            draw.line((track_start, bar_y, plane_x - 14, bar_y), fill=bar_color, width=1)
        
        # 3. DRAW THE CIRCLES: These sit at the absolute ends of the rail
        # Left Circle (Departure)
        draw.ellipse((track_start-2, bar_y-2, track_start+2, bar_y+2), fill=bar_color)
        # Right Circle (Arrival) - This will now be visible at the end of the grey rail
        draw.ellipse((track_end-2, bar_y-2, track_end+2, bar_y+2), fill=bar_color)

        # 4. DRAW THE PLANE: Overwrites the grey rail underneath
        plane_pixels, palette = icons.get_frame("SidePlane", 0)
        for i, color_idx in enumerate(plane_pixels):
            if color_idx != 0:
                px = (i % 14) + (plane_x - 14) 
                py = (i // 14) + (bar_y - 3)
                if 0 <= px < 64 and 0 <= py < 32:
                    draw.point((px, py), fill=palette.get(color_idx))
        return self.canvas