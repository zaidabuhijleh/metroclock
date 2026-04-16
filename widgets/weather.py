import time

import requests
from PIL import ImageDraw, ImageFont

import config
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

    def _measure_text(self, text, font):
        if hasattr(font, "getbbox"):
            left, _, right, _ = font.getbbox(text)
            return right - left
        return int(font.getlength(text))

    def _resolve_condition_key(self, weather_data):
        weather = weather_data["weather"][0]
        main = weather.get("main", "")
        description = weather.get("description", "").lower()
        icon_code = weather.get("icon", "")

        if "tornado" in description:
            return "tornado"
        if "squall" in description:
            return "squall"
        if "thunderstorm" in description or main == "Thunderstorm":
            return "thunderstorm"
        if "freezing rain" in description or "shower rain" in description:
            return "shower_rain"
        if "drizzle" in description or main == "Drizzle":
            return "drizzle"
        if "snow" in description or main == "Snow":
            return "snow"
        if "smoke" in description or main == "Smoke" or "ash" in description:
            return "smoke"
        if "sand" in description or "dust" in description or main in {"Dust", "Sand", "Ash"}:
            return "dust"
        if "haze" in description or main == "Haze":
            return "haze"
        if "fog" in description or "mist" in description or main in {"Mist", "Fog"}:
            return "mist"
        if "rain" in description or main == "Rain":
            return "rain"

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
            if "overcast" in description:
                return "overcast"
            return "broken_clouds"
        if icon_code.startswith("09"):
            return "shower_rain"
        if icon_code.startswith("10"):
            return "rain"
        if icon_code.startswith("11"):
            return "thunderstorm"
        if icon_code.startswith("13"):
            return "snow"
        if icon_code.startswith("50"):
            return "mist"

        return "clear_day"

    def _format_condition_label(self, weather_data):
        weather = weather_data["weather"][0]
        description = weather.get("description", "").replace("-", " ").title()
        replacements = {
            "Thunderstorm": "Storm",
            "With": "",
            "Intensity": "",
        }
        for old, new in replacements.items():
            description = description.replace(old, new)

        words = [word for word in description.split() if word]
        if not words:
            words = [weather.get("main", "Weather").title()]

        short = " ".join(words[:2])
        if len(short) > 13 and len(words) > 1:
            short = words[0]
        return short.upper()

    def _draw_icon(self, draw, key):
        pixels, palette = icons.get_frame(key, self.anim_frame)
        for index, color_code in enumerate(pixels):
            if color_code == 0:
                continue
            x = index % 21
            y = index // 21
            draw.point((x, y), fill=palette[color_code])

    def _draw_temp_block(self, draw, temp, label, accent):
        right_start = 23
        right_width = self.width - right_start - 1
        degree_sign = "\N{DEGREE SIGN}"

        temp_str = str(temp)
        temp_width = self._measure_text(temp_str, self.temp_font)
        degree_width = self._measure_text(degree_sign, self.label_font)
        total_width = temp_width + degree_width + 1
        temp_x = right_start + max(0, (right_width - total_width) // 2)
        temp_y = 3

        draw.text((temp_x, temp_y), temp_str, font=self.temp_font, fill=self.color_temp)
        draw.text(
            (temp_x + temp_width + 1, temp_y + 2),
            degree_sign,
            font=self.label_font,
            fill=self.color_degree,
        )

        label_width = self._measure_text(label, self.label_font)
        label_x = right_start + max(0, (right_width - label_width) // 2)
        label_y = 22 if label_width <= right_width else 19

        if label_width > right_width and " " in label:
            first, second = label.split(" ", 1)
            first_width = self._measure_text(first, self.label_font)
            second_width = self._measure_text(second, self.label_font)
            draw.text(
                (right_start + max(0, (right_width - first_width) // 2), 19),
                first,
                font=self.label_font,
                fill=self.color_label,
            )
            draw.text(
                (right_start + max(0, (right_width - second_width) // 2), 25),
                second,
                font=self.label_font,
                fill=self.color_label,
            )
        else:
            draw.text((label_x, label_y), label, font=self.label_font, fill=self.color_label)

        draw.line((24, 18, self.width - 3, 18), fill=accent)

    def _accent_color(self, key):
        accent_map = {
            "clear_day": (255, 196, 72),
            "clear_night": (184, 197, 255),
            "few_clouds_day": (255, 196, 72),
            "few_clouds_night": (184, 197, 255),
            "scattered_clouds": (164, 188, 219),
            "broken_clouds": (164, 188, 219),
            "overcast": (120, 142, 173),
            "drizzle": (126, 216, 255),
            "rain": (82, 174, 255),
            "shower_rain": (82, 174, 255),
            "thunderstorm": (255, 245, 140),
            "snow": (192, 248, 255),
            "mist": (156, 214, 214),
            "haze": (255, 214, 74),
            "dust": (255, 163, 51),
            "squall": (165, 234, 255),
            "tornado": (214, 196, 255),
            "smoke": (163, 176, 196),
        }
        return accent_map.get(key, self.color_separator)

    def draw(self):
        draw = ImageDraw.Draw(self.canvas)
        draw.rectangle((0, 0, self.width, self.height), fill=(0, 0, 0))

        if not self.data:
            return self.canvas

        temp = round(self.data["main"]["temp"])
        condition_key = self._resolve_condition_key(self.data)
        label = self._format_condition_label(self.data)
        accent = self._accent_color(condition_key)

        self._draw_icon(draw, condition_key)
        draw.line((21, 2, 21, self.height - 3), fill=self.color_separator)
        self._draw_temp_block(draw, temp, label, accent)

        return self.canvas
