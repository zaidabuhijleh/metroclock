import threading
import time

import requests
from PIL import Image, ImageDraw, ImageFont

import config
import config_manager
import web_server
from core import cloud_data
import widgets.icons as icons
from core.widget import Widget


class WeatherWidget(Widget):
    def __init__(self, width, height):
        super().__init__(width, height)
        self.data = None
        self.forecast_data = None
        self.anim_frame = 0
        self.last_anim = time.time()
        self.label_scroll_speed = 20
        self.label_left_padding = 3

        # Background fetch plumbing — keeps HTTP off the render thread so a slow
        # or failing OpenWeather call never stalls the matrix. Mirrors the metro
        # and stocks widgets.
        self.update_interval = 600  # current conditions
        self.forecast_interval = 1800  # forecast moves slowly; pull it less often
        self._failure_backoff_seconds = 30
        self._max_failure_backoff_seconds = 300
        self._last_forecast_fetch = 0.0
        self._last_config_reload = 0.0
        self._last_error_log_at = 0.0
        self._last_fetch_error = ""
        self._config_signature = None
        self._fetch_wake = threading.Event()
        # One session → keep-alive instead of a fresh TLS handshake per call.
        self._session = requests.Session()

        self.color_bg_top = (2, 6, 16)
        self.color_bg_bottom = (5, 13, 29)
        self.color_temp = (245, 247, 255)
        self.color_degree = (255, 196, 72)
        self.color_label = (164, 188, 219)
        self.color_separator = (29, 58, 86)

        try:
            self.temp_font = ImageFont.truetype(config.FONT_PATH_TALL, config.FONT_SIZE_TALL)
        except Exception:
            self.temp_font = ImageFont.load_default()

        try:
            self.label_font = ImageFont.truetype(config.FONT_PATH_SMALL, config.FONT_SIZE_SMALL)
        except Exception:
            self.label_font = ImageFont.load_default()

        self._worker = threading.Thread(target=self._fetch_worker, name="weather-fetch", daemon=True)
        self._worker.start()

    def update(self):
        """Lightweight: advance the icon animation, nudge the worker on config changes."""
        now = time.time()
        if now - self.last_anim > 0.45:
            self.anim_frame += 1
            self.last_anim = now

        with config_manager.CONFIG_LOCK:
            if now - self._last_config_reload >= 1.0:
                config_manager.reload_config()
                self._last_config_reload = now
            signature = self._current_config_signature()

        if signature != self._config_signature:
            self._config_signature = signature
            self._last_forecast_fetch = 0.0  # location/units changed; forecast is stale
            self._fetch_wake.set()  # refetch immediately for the new config

    def _fetch_worker(self):
        """Daemon loop — refresh on an interval, back off after failures.

        The old inline fetch only advanced its clock on HTTP 200, so a bad API
        key retried two blocking requests on every rendered frame.
        """
        failure_delay = self._failure_backoff_seconds
        while True:
            if self._fetch_once():
                failure_delay = self._failure_backoff_seconds
                wait_seconds = self.update_interval
            else:
                wait_seconds = failure_delay
                failure_delay = min(self._max_failure_backoff_seconds, failure_delay * 2)
            self._fetch_wake.wait(timeout=wait_seconds)
            self._fetch_wake.clear()

    def _fetch_once(self) -> bool:
        # Snapshot of the config this request is for; checked again before
        # anything is published.
        request_signature = self._current_config_signature()
        # A locally configured key wins, so developer units and anyone who
        # supplies their own key keep calling OpenWeather directly. Otherwise go
        # through the cloud proxy, which holds the key: a clock in the field has
        # no credentials of its own.
        api_key = str(getattr(config, "OPENWEATHER_API_KEY", "") or "").strip()
        if api_key:
            params = {**self._location_params(), "appid": api_key, "units": self._units()}
            fetch = lambda endpoint, attribute: self._fetch_direct(
                endpoint, params, attribute, request_signature
            )
        elif cloud_data.is_available():
            fetch = lambda endpoint, attribute: self._fetch_via_cloud(
                endpoint, attribute, request_signature
            )
        else:
            self._last_fetch_error = "not paired"
            return False

        if not fetch("weather", "data"):
            return False

        now = time.time()
        if now - self._last_forecast_fetch >= self.forecast_interval:
            # The timestamp is only advanced when the data was actually
            # published, so a discarded fetch does not mark the forecast fresh.
            if fetch("forecast", "forecast_data") and not self._is_stale(request_signature):
                self._last_forecast_fetch = now
        return True

    def _is_stale(self, request_signature) -> bool:
        """True when location or units changed while this request was in flight.

        The forecast timestamp is the sharp edge here: an in-flight request can
        publish the previous location's forecast and reset _last_forecast_fetch
        to "fresh", after which the new location gets no forecast for half an
        hour.
        """
        # None means the render thread has not declared what it wants yet, so
        # the first fetch of the session has nothing to conflict with.
        if self._config_signature is None or request_signature == self._config_signature:
            return False
        self._log_error("Discarding a weather fetch whose config changed mid-flight")
        return True

    def _fetch_via_cloud(self, endpoint: str, attribute: str, request_signature=None) -> bool:
        zip_code = str(getattr(config, "WEATHER_ZIP", "") or "").strip()
        params = {"units": self._units()}
        if zip_code:
            params["zip"] = zip_code
            params["country"] = str(getattr(config, "WEATHER_COUNTRY", "US") or "US").strip().upper()
        else:
            params["city_id"] = str(getattr(config, "OPENWEATHER_CITY_ID", "") or "").strip()
        try:
            payload = cloud_data.get(endpoint, params)
        except cloud_data.CloudDataError as exc:
            self._last_fetch_error = exc.reason
            self._log_error(f"Weather {endpoint} via cloud failed: {exc.reason}")
            return False
        if self._is_stale(request_signature):
            return True
        setattr(self, attribute, payload)
        self._last_fetch_error = ""
        return True

    def _fetch_direct(self, endpoint: str, params: dict, attribute: str, request_signature=None) -> bool:
        try:
            resp = self._session.get(
                f"https://api.openweathermap.org/data/2.5/{endpoint}",
                params=params,
                timeout=8,
            )
            resp.raise_for_status()
            payload = resp.json()
            if self._is_stale(request_signature):
                return True
            # Whole-object rebind: the render thread always sees a complete payload.
            setattr(self, attribute, payload)
            self._last_fetch_error = ""
            return True
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            # Shown on a 64px panel, so keep it to a few characters.
            self._last_fetch_error = f"http {status}" if status else "no network"
            # Never the exception itself: requests puts the full URL, appid
            # included, into its error strings.
            self._log_error(f"Weather {endpoint} fetch error: {type(exc).__name__}")
            return False

    def _log_error(self, message: str):
        now = time.time()
        if now - self._last_error_log_at < 60:
            return
        self._last_error_log_at = now
        print(message, flush=True)

    @staticmethod
    def _units() -> str:
        return str(getattr(config, "WEATHER_UNITS", "metric") or "metric").strip().lower()

    def _current_config_signature(self):
        return (
            str(getattr(config, "OPENWEATHER_API_KEY", "") or "").strip(),
            str(getattr(config, "OPENWEATHER_CITY_ID", "") or "").strip(),
            str(getattr(config, "WEATHER_ZIP", "") or "").strip(),
            str(getattr(config, "WEATHER_COUNTRY", "US") or "US").strip().upper(),
            self._units(),
            cloud_data.signature(),
        )

    def _placeholder_reason(self) -> str:
        if self._last_fetch_error:
            return self._last_fetch_error
        if not str(getattr(config, "OPENWEATHER_API_KEY", "") or "").strip() and not cloud_data.is_available():
            # Not "no api key": a field unit is never meant to have one.
            return "not paired"
        return "loading"

    def _draw_placeholder(self, draw):
        label = "WEATHER"
        label_width = int(self.temp_font.getlength(label))
        draw.text(
            ((self.width - label_width) // 2, 5),
            label,
            font=self.temp_font,
            fill=self.color_temp,
        )
        reason = self._placeholder_reason()
        while reason and int(self.label_font.getlength(reason)) > self.width - 4:
            reason = reason[:-1]
        reason_width = int(self.label_font.getlength(reason))
        draw.text(
            ((self.width - reason_width) // 2, 19),
            reason,
            font=self.label_font,
            fill=self.color_label,
        )

    def _location_params(self):
        zip_code = str(getattr(config, "WEATHER_ZIP", "") or "").strip()
        country = str(getattr(config, "WEATHER_COUNTRY", "US") or "US").strip().upper()
        if zip_code:
            return {"zip": f"{zip_code},{country}" if country else zip_code}
        return {"id": config.OPENWEATHER_CITY_ID}

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
            "few_clouds_day":   "Partly",
            "few_clouds_night": "Partly",
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

    def _mix(self, color_a, color_b, amount):
        amount = max(0.0, min(1.0, amount))
        return tuple(
            int(color_a[i] + (color_b[i] - color_a[i]) * amount)
            for i in range(3)
        )

    def _draw_background(self, draw, key, accent):
        for y in range(self.height):
            color = self._mix(self.color_bg_top, self.color_bg_bottom, y / max(1, self.height - 1))
            draw.line((0, y, self.width - 1, y), fill=color)

    def _draw_icon(self, draw, key):
        icon_x = 2
        pixels, palette = icons.get_frame(key, self.anim_frame)
        for index, color_code in enumerate(pixels):
            if color_code == 0:
                continue
            x = icon_x + (index % icons.WIDTH)
            y = index // icons.WIDTH
            draw.point((x, y), fill=palette[color_code])

    def _fit_text(self, text, max_width, font):
        if not text:
            return ""
        if self._font_metrics(text, font)[0] <= max_width:
            return text

        ellipsis = "."
        trimmed = text
        while trimmed and self._font_metrics(trimmed + ellipsis, font)[0] > max_width:
            trimmed = trimmed[:-1]
        return trimmed + ellipsis if trimmed else ""

    def _draw_text_clipped(self, x, y, w, h, text, font, fill, align="center"):
        if w <= 0 or h <= 0 or not text:
            return

        text = self._fit_text(str(text), w, font)
        text_w, left_off = self._font_metrics(text, font)

        if align == "left":
            text_x = -left_off
        elif align == "right":
            text_x = max(0, w - text_w) - left_off
        else:
            text_x = max(0, (w - text_w) // 2) - left_off

        patch = self.canvas.crop((x, y, x + w, y + h))
        ImageDraw.Draw(patch).text((text_x, 0), text, font=font, fill=fill)
        self.canvas.paste(patch, (x, y))

    def _label_scroll_x(self, label, available_width, font=None):
        """Returns x position relative to the right panel origin."""
        font = font or self.temp_font
        width, left_off = self._font_metrics(label, font)
        padded = available_width - self.label_left_padding
        if width <= padded:
            return self.label_left_padding + max(0, (padded - width) // 2) - left_off

        scroll_distance = width - padded
        cycle = 1.0 + (scroll_distance / self.label_scroll_speed) + 1.0
        elapsed = time.time() % cycle
        offset = 0 if elapsed < 1.0 else min(scroll_distance, (elapsed - 1.0) * self.label_scroll_speed)
        return self.label_left_padding - left_off - int(offset)

    def _unit_suffix(self):
        unit_raw = str(getattr(config, "WEATHER_UNITS", "metric") or "metric").strip().lower()
        return "F" if unit_raw in {"imperial", "f", "fahrenheit"} else "C"

    def _wind_suffix(self):
        return "MPH" if self._unit_suffix() == "F" else "M/S"

    def _current_detail_lines(self, weather_data):
        main = weather_data.get("main", {})
        wind = weather_data.get("wind", {})
        details = []

        feels_like = main.get("feels_like")
        if isinstance(feels_like, (int, float)):
            details.append(f"FL {round(feels_like)}°")

        humidity = main.get("humidity")
        if isinstance(humidity, (int, float)):
            details.append(f"HUM {round(humidity)}%")

        wind_speed = wind.get("speed")
        if isinstance(wind_speed, (int, float)):
            details.append(f"W {round(wind_speed)}{self._wind_suffix()}")

        temp_min = main.get("temp_min")
        temp_max = main.get("temp_max")
        if isinstance(temp_min, (int, float)) and isinstance(temp_max, (int, float)):
            details.append(f"H{round(temp_max)} L{round(temp_min)}")

        return details or ["LIVE NOW"]

    def _forecast_entries(self):
        if not isinstance(self.forecast_data, dict):
            return []

        now = time.time()
        entries = []
        for item in self.forecast_data.get("list", []):
            if not isinstance(item, dict):
                continue

            timestamp = item.get("dt")
            if isinstance(timestamp, (int, float)) and timestamp <= now:
                continue

            main = item.get("main", {})
            temp = main.get("temp")
            if not isinstance(temp, (int, float)):
                continue

            weather = item.get("weather") or []
            icon = weather[0].get("icon", "") if weather and isinstance(weather[0], dict) else ""
            key = self._resolve_condition_key({"weather": [{"icon": icon, "description": "", "main": ""}]})
            hours = max(1, int(round(((timestamp or now + (len(entries) + 1) * 10800) - now) / 3600)))
            entries.append({
                "hour": f"+{hours}H",
                "temp": f"{round(temp)}°",
                "accent": self._accent_color(key),
            })

            if len(entries) >= 2:
                break

        return entries

    def _should_show_forecast(self):
        return bool(self._forecast_entries()) and int(time.time() // 8) % 3 == 2

    def _draw_forecast_block(self, right_start, right_width, accent):
        entries = self._forecast_entries()
        if not entries:
            return False

        self._draw_text_clipped(
            right_start,
            2,
            right_width,
            7,
            "NEXT",
            self.label_font,
            self._mix(accent, self.color_temp, 0.22),
        )

        for row, entry in enumerate(entries[:2]):
            y = 11 + row * 10
            self._draw_text_clipped(
                right_start,
                y,
                12,
                7,
                entry["hour"],
                self.label_font,
                self._mix(entry["accent"], self.color_temp, 0.2),
                align="left",
            )
            self._draw_text_clipped(
                right_start + 13,
                y - 1,
                right_width - 13,
                10,
                entry["temp"],
                self.temp_font,
                self.color_temp,
                align="right",
            )
        return True

    def _draw_temp_block(self, draw, weather_data, temp, label, accent):
        right_start = 27
        right_width = self.width - right_start - 2
        degree_sign = "\N{DEGREE SIGN}"

        if self._should_show_forecast() and self._draw_forecast_block(right_start, right_width, accent):
            return

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

        self._draw_text_clipped(
            right_start,
            14,
            right_width,
            7,
            label,
            self.label_font,
            self._mix(self.color_label, accent, 0.12),
        )

        details = self._current_detail_lines(weather_data)
        detail = details[int(time.time() // 6) % len(details)]
        self._draw_text_clipped(
            right_start,
            24,
            right_width,
            7,
            detail,
            self.label_font,
            self._mix(accent, self.color_temp, 0.28),
        )

    def draw(self):
        self.canvas = Image.new("RGB", (self.width, self.height), self.color_bg_top)
        draw = ImageDraw.Draw(self.canvas)

        preview = web_server.get_weather_preview()
        weather_data = web_server.preview_weather_data(preview, config.WEATHER_UNITS) if preview else self.data

        if not weather_data:
            # Never return a bare canvas here. color_bg_top is near-black, so a
            # silent failure looked like a dead panel — and because the fill is
            # not pure black, the app's blank-frame safety net did not catch it
            # either. Say why instead.
            self._draw_placeholder(draw)
            return self.canvas

        temp = round(weather_data["main"]["temp"])
        condition_key = self._resolve_condition_key(weather_data)
        label = self._format_condition_label(condition_key)
        accent = self._accent_color(condition_key)

        self._draw_background(draw, condition_key, accent)
        self._draw_temp_block(draw, weather_data, temp, label, accent)
        self._draw_icon(draw, condition_key)

        return self.canvas
