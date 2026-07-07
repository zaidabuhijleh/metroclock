import time

from PIL import Image, ImageDraw, ImageFont

import config
from core.widget import Widget


class SetupStatusWidget(Widget):
    def __init__(self, width, height, status_provider):
        super().__init__(width, height)
        self._status_provider = status_provider
        try:
            self.font = ImageFont.truetype(config.FONT_PATH_SMALL, config.FONT_SIZE_SMALL)
        except Exception:
            self.font = ImageFont.load_default()

    def update(self):
        pass

    def draw(self):
        status = self._status_provider() or {}
        self.canvas = Image.new("RGB", (self.width, self.height), (0, 0, 0))
        draw = ImageDraw.Draw(self.canvas)

        ssid = str(status.get("hotspot_ssid") or "MetroClock-Setup")
        ip = str(status.get("hotspot_ip") or "192.168.4.1")
        reason = str(status.get("reason") or "WiFi setup")
        last_error = str(status.get("last_error") or "")

        if last_error:
            pages = self._error_pages(last_error)
        else:
            pages = [
                ("WIFI LOST", "SETUP MODE", reason.upper()[:16]),
                ("JOIN WIFI", ssid[:16], ""),
                ("OPEN", ip[:16], "WEB SETUP"),
            ]

        page = pages[int(time.time() // 3) % len(pages)]
        colors = [(255, 80, 60), (255, 210, 80), (120, 220, 255)]
        y_positions = [2, 12, 22]
        for idx, text in enumerate(page):
            if not text:
                continue
            self._draw_centered(draw, text, y_positions[idx], colors[idx])
        return self.canvas

    def _draw_centered(self, draw, text, y, color):
        try:
            bbox = draw.textbbox((0, 0), text, font=self.font)
            width = bbox[2] - bbox[0]
            left = bbox[0]
        except Exception:
            width = int(self.font.getlength(text)) if hasattr(self.font, "getlength") else len(text) * 4
            left = 0
        x = max(0, (self.width - width) // 2) - left
        draw.text((x, y), text, font=self.font, fill=color)

    def _error_pages(self, error):
        normalized = error.upper()
        if "HOSTAPD" in normalized and "MISSING" in normalized:
            return [
                ("HOTSPOT FAIL", "NO HOSTAPD", "RUN SETUP"),
                ("NEED PACKAGE", "HOSTAPD", "DNSMASQ"),
            ]
        if "DNSMASQ" in normalized and "MISSING" in normalized:
            return [
                ("HOTSPOT FAIL", "NO DNSMASQ", "RUN SETUP"),
                ("NEED PACKAGE", "HOSTAPD", "DNSMASQ"),
            ]
        if "RFKILL" in normalized or "BLOCKED" in normalized:
            return [
                ("WIFI BLOCKED", "CHECK RFKILL", "UNBLOCK WIFI"),
            ]
        if "HOSTAPD" in normalized:
            return [
                ("HOSTAPD FAIL", "CHECK LOGS", "SYSTEM TAB"),
                ("ERROR", normalized[:16], normalized[16:32]),
            ]
        return [
            ("HOTSPOT FAIL", "CHECK LOGS", "SYSTEM TAB"),
            ("ERROR", normalized[:16], normalized[16:32]),
        ]
