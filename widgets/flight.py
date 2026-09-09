import threading
import time
from datetime import datetime

import requests
from PIL import ImageDraw, ImageFont

import config
import config_manager
import widgets.icons as icons
from core import cloud_data
from core.widget import Widget


class FlightWidget(Widget):
    """Tracks a single flight by IATA number.

    Polling is event driven rather than periodic. AviationStack's free tier
    allows very few requests per month, so the widget sleeps until the next
    moment the answer can actually have changed - shortly before departure,
    shortly before arrival - instead of waking on a fixed interval. Nothing on
    screen changes mid-flight: the progress bar is interpolated locally from the
    departure and arrival times.
    """

    TERMINAL_STATES = {"landed", "cancelled", "diverted", "incident"}

    # Poll schedule, in seconds.
    POLL_FAR_FROM_DEPARTURE = 6 * 3600
    POLL_APPROACHING_LEAD = 2 * 3600      # wake this long before departure
    POLL_NEAR_DEPARTURE = 30 * 60
    POLL_AWAITING_TAKEOFF = 15 * 60       # departure time passed, still "scheduled"
    POLL_ARRIVAL_LEAD = 30 * 60           # wake this long before arrival
    POLL_NEAR_ARRIVAL = 15 * 60
    POLL_AFTER_LANDING = 3 * 3600         # hold the result, then look for the next leg
    POLL_NOT_FOUND = 6 * 3600
    POLL_UNKNOWN = 3600

    FAILURE_BACKOFF_SECONDS = 300
    MAX_FAILURE_BACKOFF_SECONDS = 6 * 3600

    # Circuit breaker, not a quota manager: an in-process counter cannot track a
    # monthly allowance across restarts. It exists so that a logic bug can never
    # burn the month's requests in a loop, which is what the previous version
    # did - it refetched on every rendered frame whenever data was missing.
    MAX_REQUESTS_PER_HOUR = 6

    # Layout, four bands: identity + status, the time that matters, the progress
    # rail, and the endpoints sitting under the ends of the rail they describe.
    # One font throughout (spleen 5x8). The 4x6 face is unusable here: its N is
    # two pixels different from its M in a three-column glyph, so EN ROUTE read
    # as "EM ROUTE" and NOT FOUND as "MOT FOUMD" on the panel. Hierarchy comes
    # from colour instead of size.
    ROW_HEAD_Y = 0
    ROW_TIME_Y = 8
    RAIL_Y = 20
    PLANE_TOP_Y = 17
    ROW_ENDS_Y = 24
    RAIL_X0 = 2
    RAIL_X1 = 61
    PLANE_W = 14
    PLANE_H = 6

    COLOR_GOLD = (255, 176, 32)
    COLOR_TEXT = (235, 240, 255)
    COLOR_DIM = (116, 138, 170)
    COLOR_RAIL = (44, 52, 68)
    COLOR_LIVE = (64, 220, 120)
    COLOR_WARN = (255, 86, 86)
    COLOR_COOL = (96, 176, 255)

    def __init__(self, width, height):
        super().__init__(width, height)
        self.data = None
        self.status_text = "LOADING"
        self._request_times = []
        self._config_signature = None
        self._last_config_reload = 0.0
        self._last_log_at = 0.0
        self._fetch_wake = threading.Event()
        self._session = requests.Session()

        try:
            self.font = ImageFont.truetype(config.FONT_PATH_TALL, config.FONT_SIZE_TALL)
        except Exception:
            self.font = ImageFont.load_default()
        self._worker = threading.Thread(target=self._fetch_worker, name="flight-fetch", daemon=True)
        self._worker.start()

    # ------------------------------------------------------------------ update

    def update(self):
        """Lightweight: no HTTP here. Wake the worker when the flight changes."""
        now = time.time()
        with config_manager.CONFIG_LOCK:
            if now - self._last_config_reload >= 1.0:
                config_manager.reload_config()
                self._last_config_reload = now
            signature = self._current_config_signature()

        if signature != self._config_signature:
            self._config_signature = signature
            self.data = None
            self.status_text = "LOADING"
            self._fetch_wake.set()

    @staticmethod
    def _current_config_signature():
        return (
            str(getattr(config, "FLIGHT_NUMBER", "") or "").strip().upper(),
            str(getattr(config, "AVIATIONSTACK_API_KEY", "") or "").strip(),
            # Without this, a clock that pairs during onboarding would sit on a
            # placeholder for up to six hours before its next scheduled poll.
            cloud_data.signature(),
        )

    # ---------------------------------------------------------------- fetching

    def _fetch_worker(self):
        failure_delay = self.FAILURE_BACKOFF_SECONDS
        while True:
            if self._fetch_once():
                failure_delay = self.FAILURE_BACKOFF_SECONDS
                delay = self._next_poll_delay()
            else:
                delay = failure_delay
                failure_delay = min(self.MAX_FAILURE_BACKOFF_SECONDS, failure_delay * 2)
            self._fetch_wake.wait(timeout=max(60.0, float(delay)))
            self._fetch_wake.clear()

    def _allow_request(self) -> bool:
        now = time.time()
        self._request_times = [t for t in self._request_times if now - t < 3600]
        if len(self._request_times) >= self.MAX_REQUESTS_PER_HOUR:
            return False
        self._request_times.append(now)
        return True

    def _fetch_once(self) -> bool:
        api_key = str(getattr(config, "AVIATIONSTACK_API_KEY", "") or "").strip()
        flight_number = str(getattr(config, "FLIGHT_NUMBER", "") or "").strip().upper()
        if not flight_number:
            self.status_text = "NO FLIGHT"
            return False
        if not self._allow_request():
            self._log("Flight fetch skipped: hourly request cap reached")
            return False

        # A locally configured key wins; otherwise use the cloud proxy, which
        # holds the key. A clock in the field has no credentials of its own.
        if not api_key:
            if not cloud_data.is_available():
                self.status_text = "NOT PAIRED"
                return False
            return self._fetch_via_cloud(flight_number)

        try:
            response = self._session.get(
                "https://api.aviationstack.com/v1/flights",
                params={"access_key": api_key, "flight_iata": flight_number},
                timeout=10,
            )
        except Exception as exc:
            # Never the exception itself: requests puts the full URL, and so
            # the access_key, into its error strings.
            self._log(f"Flight API error: {type(exc).__name__}")
            self.status_text = "NO NETWORK"
            return False

        if response.status_code != 200:
            self._log(f"Flight API status {response.status_code}")
            self.status_text = f"ERR {response.status_code}"
            return False

        try:
            payload = response.json()
        except Exception:
            self.status_text = "BAD DATA"
            return False

        # apilayer answers 200 with an error body for plan and quota problems,
        # so a 200 is not on its own a success.
        error = payload.get("error") if isinstance(payload, dict) else None
        if error:
            code = str(error.get("code") or "error")
            self._log(f"Flight API error: {error}")
            self.status_text = code.replace("_", " ").upper()[:12]
            return False

        rows = payload.get("data") or []
        if not rows:
            # A valid answer: no such flight today. Use the normal schedule
            # rather than the failure backoff.
            self.data = None
            self.status_text = "NOT FOUND"
            return True

        self.data = rows[0] if isinstance(rows[0], dict) else None
        self.status_text = None if self.data else "BAD DATA"
        return True

    def _fetch_via_cloud(self, flight_number: str) -> bool:
        """Fetch through the cloud proxy, which returns an already-normalised record.

        The payload is the subset of fields this widget reads, so swapping flight
        provider is a change in the cloud service and not a firmware update here.
        """
        try:
            payload = cloud_data.get("flight", {"number": flight_number})
        except cloud_data.CloudDataError as exc:
            self._log(f"Flight via cloud failed: {exc.reason}")
            self.status_text = exc.reason.upper()[:12]
            return False

        if not isinstance(payload, dict):
            self.status_text = "BAD DATA"
            return False
        if not payload.get("found"):
            # A real answer, not a failure: use the normal schedule.
            self.data = None
            self.status_text = "NOT FOUND"
            return True

        record = payload.get("data")
        self.data = record if isinstance(record, dict) else None
        self.status_text = None if self.data else "BAD DATA"
        return True

    def _next_poll_delay(self) -> float:
        if not self.data:
            return self.POLL_NOT_FOUND

        status = self._raw_status()
        now = time.time()

        if status in self.TERMINAL_STATES:
            return self.POLL_AFTER_LANDING

        if status == "active":
            arrival = self._leg_timestamp("arrival")
            if arrival is None:
                return self.POLL_NEAR_ARRIVAL
            # Nothing displayed changes while airborne, so sleep until shortly
            # before arrival, when the ETA can still move.
            lead = arrival - self.POLL_ARRIVAL_LEAD - now
            return lead if lead > self.POLL_NEAR_ARRIVAL else self.POLL_NEAR_ARRIVAL

        departure = self._leg_timestamp("departure")
        if departure is None:
            return self.POLL_UNKNOWN
        until_departure = departure - now
        if until_departure <= 0:
            return self.POLL_AWAITING_TAKEOFF
        if until_departure > 12 * 3600:
            return self.POLL_FAR_FROM_DEPARTURE
        if until_departure > self.POLL_APPROACHING_LEAD:
            return until_departure - self.POLL_APPROACHING_LEAD
        return self.POLL_NEAR_DEPARTURE

    def _log(self, message):
        now = time.time()
        if now - self._last_log_at < 60:
            return
        self._last_log_at = now
        print(message, flush=True)

    # ------------------------------------------------------------- data access

    @staticmethod
    def _parse_api_time(value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except Exception:
            return None

    def _leg(self, leg):
        section = self.data.get(leg) if isinstance(self.data, dict) else None
        return section if isinstance(section, dict) else {}

    def _leg_timestamp(self, leg):
        section = self._leg(leg)
        return self._parse_api_time(section.get("estimated") or section.get("scheduled"))

    def _leg_local_time(self, leg):
        """Formatted in the airport's own timezone, which is what a traveller wants."""
        section = self._leg(leg)
        raw = section.get("estimated") or section.get("scheduled")
        if not raw:
            return "--:--"
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).strftime("%H:%M")
        except Exception:
            return "--:--"

    def _raw_status(self):
        if not isinstance(self.data, dict):
            return ""
        return str(self.data.get("flight_status") or "").strip().lower()

    def _flight_label(self):
        flight = self.data.get("flight") if isinstance(self.data, dict) else None
        if isinstance(flight, dict):
            label = str(flight.get("iata") or flight.get("icao") or "").strip().upper()
            if label:
                return label
        return str(getattr(config, "FLIGHT_NUMBER", "") or "").strip().upper() or "----"

    def _airport_code(self, leg):
        section = self._leg(leg)
        code = str(section.get("iata") or section.get("icao") or "").strip().upper()
        return code[:4] if code else "---"

    # Full label, plus a short form for when the flight number is long enough
    # that the full one would collide with it.
    STATUS_LABELS = {
        "active": ("EN ROUTE", "ENRT", "COLOR_LIVE"),
        "landed": ("LANDED", "LAND", "COLOR_LIVE"),
        "scheduled": ("SCHEDULED", "SCHED", "COLOR_COOL"),
        "delayed": ("DELAYED", "DELAY", "COLOR_WARN"),
        "cancelled": ("CANCELLED", "CNCL", "COLOR_WARN"),
        "diverted": ("DIVERTED", "DVRT", "COLOR_WARN"),
        "incident": ("INCIDENT", "INCD", "COLOR_WARN"),
    }

    def _status_display(self):
        status = self._raw_status()
        entry = self.STATUS_LABELS.get(status)
        if entry is None:
            short = (status.upper() or "UNKNOWN")[:8]
            return short, short[:5], self.COLOR_DIM
        full, short, color_name = entry
        return full, short, getattr(self, color_name)

    def _progress(self):
        status = self._raw_status()
        if status in ("landed", "diverted"):
            return 1.0
        if status != "active":
            return 0.0
        departure = self._leg_timestamp("departure")
        arrival = self._leg_timestamp("arrival")
        if not departure or not arrival:
            return 0.5
        duration = arrival - departure
        if duration <= 0:
            return 0.5
        return max(0.02, min(0.98, (time.time() - departure) / duration))

    # --------------------------------------------------------------- rendering

    @staticmethod
    def _text_width(draw, text, font):
        box = draw.textbbox((0, 0), text, font=font)
        return box[2] - box[0]

    def draw(self):
        draw = ImageDraw.Draw(self.canvas)
        draw.rectangle((0, 0, self.width, self.height), fill=(0, 0, 0))

        if not isinstance(self.data, dict):
            self._draw_placeholder(draw)
            return self.canvas

        status = self._raw_status()
        status_full, status_short, status_color = self._status_display()
        grounded = status in ("cancelled", "incident")

        # Band 1: flight number left, status right. Pick the status form that
        # actually fits the space the flight number leaves, so a six-character
        # number and a long status cannot run together.
        flight_label = self._flight_label()
        draw.text((1, self.ROW_HEAD_Y), flight_label, font=self.font, fill=self.COLOR_GOLD)
        # 1px margin each side, 2px minimum gap. Tuned so that a 4-character
        # flight number still leaves room for the full "EN ROUTE" (40px) rather
        # than dropping to the abbreviation with a pixel to spare.
        available = self.width - 4 - self._text_width(draw, flight_label, self.font)
        status_label = status_full
        if self._text_width(draw, status_label, self.font) > available:
            status_label = status_short
        while status_label and self._text_width(draw, status_label, self.font) > available:
            status_label = status_label[:-1]
        if status_label:
            status_width = self._text_width(draw, status_label, self.font)
            draw.text(
                (self.width - 1 - status_width, self.ROW_HEAD_Y + 1),
                status_label,
                font=self.font,
                fill=status_color,
            )

        # Band 2: the single time that matters for the current state. A flight
        # that is not going anywhere has no arrival estimate to show.
        if grounded or status in ("scheduled", "delayed"):
            label, value = "DEP", self._leg_local_time("departure")
        else:
            label, value = "ETA", self._leg_local_time("arrival")
        draw.text((1, self.ROW_TIME_Y), label, font=self.font, fill=self.COLOR_DIM)
        label_width = self._text_width(draw, label, self.font)
        draw.text((1 + label_width + 3, self.ROW_TIME_Y), value, font=self.font, fill=self.COLOR_TEXT)

        # Band 3: progress rail. The plane travels within the rail so it is
        # always fully on screen rather than sliding off either end. A cancelled
        # flight gets a bare rail and no aircraft - there is no journey to show.
        draw.line((self.RAIL_X0, self.RAIL_Y, self.RAIL_X1, self.RAIL_Y), fill=self.COLOR_RAIL)
        if not grounded:
            progress = self._progress()
            travel = self.RAIL_X1 - self.PLANE_W - self.RAIL_X0
            plane_x = int(self.RAIL_X0 + progress * travel)
            if plane_x > self.RAIL_X0:
                draw.line((self.RAIL_X0, self.RAIL_Y, plane_x, self.RAIL_Y), fill=status_color)
            pixels, palette = icons.get_frame("SidePlane", 0)
            for index, color_index in enumerate(pixels):
                if not color_index:
                    continue
                px = plane_x + (index % self.PLANE_W)
                py = self.PLANE_TOP_Y + (index // self.PLANE_W)
                if 0 <= px < self.width and 0 <= py < self.height:
                    draw.point((px, py), fill=palette.get(color_index))

        # Band 4: endpoints, under the ends of the rail they describe.
        origin = self._airport_code("departure")
        destination = self._airport_code("arrival")
        draw.text((1, self.ROW_ENDS_Y), origin, font=self.font, fill=self.COLOR_DIM)
        destination_width = self._text_width(draw, destination, self.font)
        draw.text(
            (max(1, self.width - 1 - destination_width), self.ROW_ENDS_Y),
            destination,
            font=self.font,
            fill=self.COLOR_DIM,
        )
        return self.canvas

    def _draw_placeholder(self, draw):
        title = "FLIGHT"
        title_width = self._text_width(draw, title, self.font)
        draw.text(((self.width - title_width) // 2, 6), title, font=self.font, fill=self.COLOR_GOLD)
        reason = str(self.status_text or "NO DATA")
        while reason and self._text_width(draw, reason, self.font) > self.width - 2:
            reason = reason[:-1]
        reason_width = self._text_width(draw, reason, self.font)
        draw.text(
            ((self.width - reason_width) // 2, 19),
            reason,
            font=self.font,
            fill=self.COLOR_DIM,
        )
