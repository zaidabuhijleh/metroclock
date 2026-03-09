import time
import requests
from PIL import Image, ImageDraw, ImageFont
from core.widget import Widget
import config
import widgets.icons as icons

class WeatherWidget(Widget):
    def __init__(self, width, height):
        super().__init__(width, height)
        self.last_fetch = 0
        self.data = None
        self.update_interval = 600 
        self.anim_frame = 0
        self.last_anim = time.time()

        # COLOR PALETTE: Dusk Theme
        self.COLOR_TEMP = (255, 180, 0)   # Soft Gold
        self.COLOR_DESC = (180, 80, 255) # Periwinkle (Blue/Purple mix)

        try:
            self.font = ImageFont.truetype(config.FONT_PATH_TALL, 10)
        except:
            self.font = ImageFont.load_default()

    def update(self):
        now = time.time()
        # Animation speed: change frame every 0.5s
        if now - self.last_anim > 0.5:
            self.anim_frame += 1
            self.last_anim = now

        if now - self.last_fetch < self.update_interval:
            return

        url = f"https://api.openweathermap.org/data/2.5/weather?id={config.OPENWEATHER_CITY_ID}&appid={config.OPENWEATHER_API_KEY}&units={config.WEATHER_UNITS}"
        try:
            resp = requests.get(url)
            if resp.status_code == 200:
                self.data = resp.json()
                self.last_fetch = now
        except:
            pass

    def draw(self):
        draw = ImageDraw.Draw(self.canvas)
        draw.rectangle((0,0, self.width, self.height), fill=(0,0,0))

        if not self.data:
            return self.canvas

        temp = int(self.data['main']['temp'])
        desc = self.data['weather'][0]['main']

        # --- LEFT 1/3: 21px ICON ---
        current_pixels, palette = icons.get_frame(desc, self.anim_frame)
        for i, color_code in enumerate(current_pixels):
            if color_code == 0: continue
            x = i % 21
            y = i // 21
            draw.point((x, y), fill=palette[color_code])

        # --- RIGHT 2/3: INFO (22 to 64) ---
        RIGHT_START = 22
        RIGHT_WIDTH = 42

        # Temp (Centered in top-right)
        temp_str = f"{temp}°"
        tw = self.font.getlength(temp_str)
        tx = RIGHT_START + (RIGHT_WIDTH - tw) // 2
        draw.text((tx, 4), temp_str, font=self.font, fill=self.COLOR_TEMP)

        # Desc (Centered in bottom-right)
        dw = self.font.getlength(desc)
        dx = RIGHT_START + (RIGHT_WIDTH - dw) // 2
        
        # Prevent clipping for long words
        if dx < RIGHT_START + 2: dx = RIGHT_START + 2
            
        draw.text((dx, 16), desc, font=self.font, fill=self.COLOR_DESC)

        return self.canvas