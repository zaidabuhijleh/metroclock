import time

import requests
from PIL import Image, ImageDraw, ImageFont

import config
import web_server
import widgets.icons as icons
from core.widget import Widget


class WeatherWidget(Widget):
    def __init__(self, width, height):
        super().__init__(width, height)
        self.last_fetch = 0
        self.data = None
        self.update_interval = 600
        self.anim_frame = 0
        self.last_anim = time.time()
        self.label_scroll_speed = 20
        self.label_left_padding = 3

        self.color_temp = (245, 247, 255)
        self.color_degree = (255, 196, 72)
        self.color_label = (164, 188, 219)
        self.color_separator = (48, 69, 92)

        try:
            self.temp_font = ImageFont.truetype(config.FONT_PATH_TALL, 10)
        except Exception:
            self.temp_font = ImageFont.load_default()

        try:
            self.label_font = ImageFont.truetype(config.FONT_PATH_SMALL, 6)
        except Exception:
            self.label_font = ImageFont.load_default()

    def update(self):
        now = time.time()
        if now - self.last_anim > 0.45:
            self.anim_frame += 1
            self.last_anim = now

        if now - self.last_fetch < self.update_interval:
            return

        url = (
            "https://api.openweathermap.org/data/2.5/weather"
            f"?id={config.OPENWEATHER_CITY_ID}"
            f"&appid={config.OPENWEATHER_API_KEY}"
            f"&units={config.WEATHER_UNITS}"
        )
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                self.data = resp.json()
                self.last_fetch = now
        except Exception:
            pass

    def _font_metrics(self, text, font):
        """Returns (width, left_offset) for the given text and font."""
        if hasattr(font, "getbbox"):
            left, _, right, _ = font.getbbox(text)
            return right - left, left
        return int(font.getlength(text)), 0

    def _resolve_condition_key(self, weather_data):
        weather = weather_data["weather"][0]
        main = weather.get("main", "")
        description = weather.get("description", "").lower()
        icon_code = weather.get("icon", "")

        if "thunderstorm" in description or main == "Thunderstorm":
            return "thunderstorm"
        if "drizzle" in description or main == "Drizzle":
            return "drizzle"
        if "snow" in description or main == "Snow":
            return "snow"
        if "rain" in description or "shower" in description or main == "Rain":
            return "rain"
        if "tornado" in description or main == "Tornado":
            return "tornado"
        if "squall" in description or main == "Squall":
            return "squall"
        if "smoke" in description or "ash" in description or main in {"Smoke", "Ash"}:
            return "smoke"
        if "dust" in description or "sand" in description or main in {"Dust", "Sand"}:
            return "dust"
        if "haze" in description or main == "Haze":
            return "haze"
        if "fog" in description or "mist" in description or main in {"Fog", "Mist"}:
            return "mist"

        if icon_code == "01d":
            return "clear_day"
        if icon_code == "01n":
            return "clear_night"
        if icon_code == "02d":
            return "few_clouds_day"
        if icon_code == "02n":
            return "few_clouds_night"
        if icon_code.startswith("03"):
            return "scattered_clouds"
        if icon_code.startswith("04"):
            return "cloudy"
        if icon_code.startswith("10"):
            return "rain"
        if icon_code.startswith("11"):
            return "thunderstorm"
        if icon_code.startswith("13"):
            return "snow"
        if icon_code.startswith("50"):
            return "mist"

        return "clear_day"

    def _format_condition_label(self, condition_key):
        labels = {
            "clear_day":        "Clear",
            "clear_night":      "Clear",
            "few_clouds_day":   "P. Cloudy",
            "few_clouds_night": "P. Cloudy",
            "scattered_clouds": "Cloudy",
            "cloudy":           "Cloudy",
            "drizzle":          "Drizzle",
            "rain":             "Rain",
            "thunderstorm":     "Storm",
            "snow":             "Snow",
            "mist":             "Mist",
            "haze":             "Haze",
            "dust":             "Dusty",
            "squall":           "Squall",
            "tornado":          "Tornado",
            "smoke":            "Smoke",
        }
        return labels.get(condition_key, "Weather")

    def _accent_color(self, key):
        accent_map = {
            "clear_day":        (255, 196, 72),
            "clear_night":      (184, 197, 255),
            "few_clouds_day":   (255, 210, 100),
            "few_clouds_night": (184, 197, 255),
            "scattered_clouds": (164, 188, 219),
            "cloudy":           (164, 188, 219),
            "drizzle":          (126, 216, 255),
            "rain":             (82, 174, 255),
            "thunderstorm":     (255, 245, 140),
            "snow":             (192, 248, 255),
            "mist":             (156, 214, 214),
            "haze":             (255, 210, 100),
            "dust":             (255, 180, 80),
            "squall":           (82, 174, 255),
            "tornado":          (176, 176, 186),
            "smoke":            (176, 176, 186),
        }
        return accent_map.get(key, self.color_separator)

    def _draw_icon(self, draw, key):
        pixels, palette = icons.get_frame(key, self.anim_frame)
        for index, color_code in enumerate(pixels):
            if color_code == 0:
                continue
            x = index % 21
            y = index // 21
            draw.point((x, y), fill=palette[color_code])

    def _label_scroll_x(self, label, available_width):
        """Returns x position relative to the right panel origin."""
        width, left_off = self._font_metrics(label, self.temp_font)
        padded = available_width - self.label_left_padding
        if width <= padded:
            return self.label_left_padding + max(0, (padded - width) // 2) - left_off

        scroll_distance = width - padded
        cycle = 1.0 + (scroll_distance / self.label_scroll_speed) + 1.0
        elapsed = time.time() % cycle
        offset = 0 if elapsed < 1.0 else min(scroll_distance, (elapsed - 1.0) * self.label_scroll_speed)
        return self.label_left_padding - left_off - int(offset)

    def _draw_temp_block(self, draw, temp, label, accent):
        right_start = 23
        right_width = self.width - right_start - 1
        degree_sign = "\N{DEGREE SIGN}"

        temp_str = str(temp)
        temp_w, temp_off = self._font_metrics(temp_str, self.temp_font)
        deg_w,  deg_off  = self._font_metrics(degree_sign, self.temp_font)
        total_w = temp_w + deg_w + 1
        temp_x = right_start + max(0, (right_width - total_w) // 2)

        draw.text((temp_x - temp_off, 2), temp_str, font=self.temp_font, fill=self.color_temp)
        draw.text(
            (temp_x + temp_w + 1 - deg_off, 2),
            degree_sign,
            font=self.temp_font,
            fill=self.color_degree,
        )

        draw.line((24, 17, self.width - 3, 17), fill=accent)

        # Label rendered into a clipped sub-image so it can't bleed into the icon area.
        label_y = 20
        label_img = Image.new("RGB", (right_width, self.height - label_y), (0, 0, 0))
        ImageDraw.Draw(label_img).text(
            (self._label_scroll_x(label, right_width), 0),
            label,
            font=self.temp_font,
            fill=self.color_label,
        )
        self.canvas.paste(label_img, (right_start, label_y))

    def draw(self):
        self.canvas = Image.new("RGB", (self.width, self.height), (0, 0, 0))
        draw = ImageDraw.Draw(self.canvas)

        preview = web_server.get_weather_preview()
        weather_data = web_server.preview_weather_data(preview, config.WEATHER_UNITS) if preview else self.data

        if not weather_data:
            return self.canvas

        temp = round(weather_data["main"]["temp"])
        condition_key = self._resolve_condition_key(weather_data)
        label = self._format_condition_label(condition_key)
        accent = self._accent_color(condition_key)

        self._draw_temp_block(draw, temp, label, accent)
        self._draw_icon(draw, condition_key)
        draw.line((21, 2, 21, self.height - 3), fill=self.color_separator)

        return self.canvas
