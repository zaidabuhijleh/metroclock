import importlib
import json
import os
import re
import time

import requests
from PIL import ImageDraw, ImageFont

import config
from core.widget import Widget
from widgets.metrolines import NYC_LINE_COLORS, TTC_LINE_COLORS, WMATA_LINE_COLORS

try:
    from google.transit import gtfs_realtime_pb2
except Exception:
    gtfs_realtime_pb2 = None


# --- PIXEL PERFECT LETTER MAPS ---
BITMAP_LETTERS = {
    "A": [(1, 0), (0, 1), (2, 1), (0, 2), (1, 2), (2, 2), (0, 3), (2, 3), (0, 4), (2, 4)],
    "B": [(0, 0), (1, 0), (0, 1), (2, 1), (0, 2), (1, 2), (0, 3), (2, 3), (0, 4), (1, 4)],
    "C": [(1, 0), (2, 0), (0, 1), (0, 2), (0, 3), (1, 4), (2, 4)],
    "D": [(0, 0), (1, 0), (0, 1), (2, 1), (0, 2), (2, 2), (0, 3), (2, 3), (0, 4), (1, 4)],
    "E": [(0, 0), (1, 0), (2, 0), (0, 1), (0, 2), (1, 2), (0, 3), (0, 4), (1, 4), (2, 4)],
    "F": [(0, 0), (1, 0), (2, 0), (0, 1), (0, 2), (1, 2), (0, 3), (0, 4)],
    "G": [(1, 0), (2, 0), (0, 1), (0, 2), (2, 2), (0, 3), (2, 3), (1, 4), (2, 4)],
    "J": [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2), (2, 3), (0, 4), (1, 4)],
    "L": [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (1, 4), (2, 4)],
    "M": [(0, 0), (2, 0), (0, 1), (1, 1), (2, 1), (0, 2), (2, 2), (0, 3), (2, 3), (0, 4), (2, 4)],
    "N": [(0, 0), (2, 0), (0, 1), (1, 1), (2, 1), (0, 2), (1, 2), (2, 2), (0, 3), (2, 3), (0, 4), (2, 4)],
    "O": [(1, 0), (0, 1), (2, 1), (0, 2), (2, 2), (0, 3), (2, 3), (1, 4)],
    "Q": [(1, 0), (0, 1), (2, 1), (0, 2), (2, 2), (0, 3), (2, 3), (1, 4), (2, 4)],
    "R": [(0, 0), (1, 0), (2, 0), (0, 1), (2, 1), (0, 2), (1, 2), (0, 3), (2, 3), (0, 4), (2, 4)],
    "S": [(1, 0), (2, 0), (0, 1), (1, 2), (2, 3), (0, 4), (1, 4)],
    "W": [(0, 0), (2, 0), (0, 1), (2, 1), (0, 2), (2, 2), (0, 3), (1, 3), (2, 3), (1, 4)],
    "Y": [(0, 0), (2, 0), (0, 1), (2, 1), (1, 2), (1, 3), (1, 4)],
    "Z": [(0, 0), (1, 0), (2, 0), (2, 1), (1, 2), (0, 3), (0, 4), (1, 4), (2, 4)],
}

BITMAP_DIGITS = {
    "0": [(1, 0), (2, 0), (0, 1), (3, 1), (0, 2), (3, 2), (0, 3), (3, 3), (1, 4), (2, 4)],
    "1": [(1, 0), (2, 0), (2, 1), (2, 2), (2, 3), (1, 4), (2, 4), (3, 4)],
    "2": [(1, 0), (2, 0), (3, 0), (0, 1), (3, 1), (2, 2), (1, 3), (0, 4), (1, 4), (2, 4), (3, 4)],
    "3": [(0, 0), (1, 0), (2, 0), (2, 1), (1, 2), (2, 2), (2, 3), (0, 4), (1, 4), (2, 4)],
    "4": [(0, 0), (2, 0), (0, 1), (2, 1), (0, 2), (1, 2), (2, 2), (2, 3), (2, 4)],
    "5": [(0, 0), (1, 0), (2, 0), (3, 0), (0, 1), (0, 2), (1, 2), (2, 2), (3, 3), (0, 4), (1, 4), (2, 4)],
    "6": [(1, 0), (2, 0), (3, 0), (0, 1), (0, 2), (1, 2), (2, 2), (0, 3), (3, 3), (1, 4), (2, 4)],
    "7": [(0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (2, 2), (2, 3), (1, 4)],
    "8": [(1, 0), (2, 0), (0, 1), (3, 1), (1, 2), (2, 2), (0, 3), (3, 3), (1, 4), (2, 4)],
    "9": [(1, 0), (2, 0), (0, 1), (3, 1), (1, 2), (2, 2), (3, 2), (3, 3), (0, 4), (1, 4), (2, 4)],
}

TTC_ROUTE_TO_LINE = {
    "yonge-university-spadina_subway": "1",
    "bloor-danforth_subway": "2",
    "scarborough_rt": "3",
    "sheppard_subway": "4",
}


class MetroWidget(Widget):
    def __init__(self, width, height):
        super().__init__(width, height)
        self.trains = []
        self.scroll_index = 0
        self.last_fetch = 0.0
        self._config_signature = None

        # Animation state
        self.page_start_time = time.time()
        self.scroll_speed = 20

        try:
            self.font_tall = ImageFont.truetype(config.FONT_PATH_TALL, 10)
        except Exception:
            self.font_tall = ImageFont.load_default()

        try:
            self.font_small = ImageFont.truetype(config.FONT_PATH_SMALL, 6)
        except Exception:
            self.font_small = ImageFont.load_default()

        self._nyc_stop_name_map = self._load_nyc_stop_name_map()

    def update(self):
        """Fetch arrival data from configured metro system."""
        now = time.time()
        importlib.reload(config)

        signature = self._current_config_signature()
        if signature != self._config_signature:
            self._config_signature = signature
            self._invalidate_cached_rows(now)
            self.last_fetch = 0.0

        if now - self.last_fetch <= 30:
            return

        system = self._metro_system()
        if system == "nyc":
            self._fetch_nyc()
        elif system == "ttc":
            self._fetch_ttc()
        else:
            self._fetch_wmata()

        self.last_fetch = now

    def _current_config_signature(self):
        return (
            self._metro_system(),
            tuple(self._wmata_station_codes()),
            str(getattr(config, "WMATA_API_KEY", "") or "").strip(),
            tuple(sorted(self._wmata_line_filter())),
            tuple(self._nyc_feed_urls()),
            tuple(sorted(self._nyc_stop_ids())),
            tuple(sorted(self._nyc_line_filter())),
            str(getattr(config, "TTC_STATION_ID", "") or "").strip().lower(),
            tuple(sorted(self._ttc_stop_uris())),
            tuple(sorted(self._ttc_line_filter())),
            self._arrival_window(),
            self._metro_page_transition(),
        )

    def _invalidate_cached_rows(self, now):
        self.trains = []
        self.scroll_index = 0
        self.page_start_time = now

    def _metro_system(self):
        value = str(getattr(config, "METRO_SYSTEM", "wmata") or "wmata").strip().lower()
        if value in {"nyc", "ttc"}:
            return value
        return "wmata"

    def _metro_page_transition(self):
        value = str(getattr(config, "METRO_PAGE_TRANSITION", "slide") or "slide").strip().lower()
        return "cut" if value == "cut" else "slide"

    def _fetch_wmata(self):
        headers = {}
        key = str(getattr(config, "WMATA_API_KEY", "") or "").strip()
        if key:
            headers["api_key"] = key

        station_codes = self._wmata_station_codes()
        if not station_codes:
            self._replace_trains([], time.time())
            return

        valid = []

        for station_code in station_codes:
            try:
                url = f"https://api.wmata.com/StationPrediction.svc/json/GetPrediction/{station_code}"
                resp = requests.get(url, headers=headers, timeout=6)
                data = resp.json()
            except Exception as exc:
                print(f"WMATA API Error ({station_code}): {exc}")
                continue

            if "Trains" not in data:
                continue

            for train in data.get("Trains", []):
                line = str(train.get("Line", "") or "").strip().upper()
                dest = str(train.get("Destination", "") or "").strip()
                if not line or line == "--":
                    continue
                line = line[:2]
                if not self._is_wmata_line_enabled(line):
                    continue
                if dest in {"No Passenger", "Train", ""} or "ssenge" in dest:
                    continue

                mins = self._normalize_wmata_mins(train.get("Min"))
                if mins == "--":
                    continue
                mins_int = int(mins)
                if not self._is_in_arrival_window(mins_int):
                    continue

                valid.append(
                    {
                        "Line": line,
                        "Destination": dest,
                        "Min": mins,
                    }
                )

        deduped = []
        seen = set()
        for row in sorted(valid, key=lambda item: (int(item["Min"]), item["Line"], item["Destination"])):
            key = (row["Line"], row["Destination"], row["Min"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)

        self._replace_trains(deduped, time.time())

    def _fetch_nyc(self):
        if gtfs_realtime_pb2 is None:
            print("NYC API Error: missing gtfs-realtime-bindings")
            return

        feed_urls = self._nyc_feed_urls()
        stop_ids = self._nyc_stop_ids()
        if not feed_urls or not stop_ids:
            self._replace_trains([], time.time())
            return

        now_ts = int(time.time())
        arrivals = []

        for feed_url in feed_urls:
            try:
                response = requests.get(feed_url, timeout=6)
                if response.status_code != 200:
                    print(f"NYC API Error: status {response.status_code} for {feed_url}")
                    continue

                feed = gtfs_realtime_pb2.FeedMessage()
                feed.ParseFromString(response.content)
            except Exception as exc:
                print(f"NYC API Error for {feed_url}: {exc}")
                continue

            for entity in feed.entity:
                if not entity.HasField("trip_update"):
                    continue

                trip_update = entity.trip_update
                route = self._normalize_nyc_route_id(getattr(trip_update.trip, "route_id", ""))
                if not route:
                    continue
                if not self._is_nyc_line_enabled(route):
                    continue

                trip_id = str(getattr(trip_update.trip, "trip_id", "") or "")
                for stop_update in trip_update.stop_time_update:
                    stop_id = str(getattr(stop_update, "stop_id", "") or "").upper()
                    if stop_id not in stop_ids:
                        continue

                    eta_minutes = self._gtfs_eta_minutes(stop_update, now_ts)
                    if eta_minutes is None:
                        continue
                    if not self._is_in_arrival_window(eta_minutes):
                        continue

                    arrivals.append(
                        {
                            "line": route,
                            "destination": self._nyc_destination_name(route, trip_update, stop_id),
                            "mins": str(eta_minutes),
                            "eta": eta_minutes,
                            "trip_id": trip_id,
                            "stop_id": stop_id,
                        }
                    )
                    # Only keep the first prediction for this stop on this trip.
                    break

        arrivals.sort(key=lambda item: (item["eta"], item["line"], item["destination"]))
        deduped = self._dedupe_nyc_arrivals(arrivals)

        trains = [
            {
                "Line": row["line"],
                "Destination": row["destination"],
                "Min": row["mins"],
            }
            for row in deduped
        ]
        self._replace_trains(trains, time.time())

    def _fetch_ttc(self):
        station_id = self._ttc_station_id()
        stop_uris = self._ttc_stop_uris()
        if not stop_uris:
            self._replace_trains([], time.time())
            return

        now_ts = int(time.time())
        arrivals = []
        source_count = 0

        for stop_uri in stop_uris:
            try:
                url = f"https://myttc.ca/{stop_uri}.json"
                resp = requests.get(url, timeout=8)
                if resp.status_code != 200:
                    print(f"TTC API Error: status {resp.status_code} for {url}")
                    continue
                data = resp.json()
            except Exception as exc:
                print(f"TTC API Error for {stop_uri}: {exc}")
                continue

            source_count += 1
            arrivals.extend(self._ttc_collect_arrivals(data, now_ts, {stop_uri}))

        # Fallback for old configs where stop URIs may be stale but station slug is valid.
        if source_count == 0 and station_id:
            try:
                url = f"https://myttc.ca/{station_id}.json"
                resp = requests.get(url, timeout=8)
                if resp.status_code == 200:
                    arrivals.extend(self._ttc_collect_arrivals(resp.json(), now_ts, set(stop_uris)))
            except Exception as exc:
                print(f"TTC API fallback error for {station_id}: {exc}")

        arrivals.sort(key=lambda item: (item["eta"], item["line"], item["destination"]))
        deduped = self._dedupe_ttc_arrivals(arrivals)
        trains = [
            {
                "Line": row["line"],
                "Destination": row["destination"],
                "Min": row["mins"],
            }
            for row in deduped
        ]
        self._replace_trains(trains, time.time())

    def _ttc_collect_arrivals(self, data, now_ts, allowed_stop_uris):
        output = []
        allowed = {str(uri or "").strip().lower() for uri in (allowed_stop_uris or set()) if str(uri or "").strip()}

        for stop in data.get("stops", []):
            stop_uri = str(stop.get("uri", "") or "").strip().lower()
            if allowed and stop_uri not in allowed:
                continue

            for route in stop.get("routes", []):
                route_uri = str(route.get("uri", "") or "").strip().lower()
                route_name = str(route.get("name", "") or "").strip()
                route_group_id = str(route.get("route_group_id", "") or "").strip()
                line = self._ttc_route_to_line(route_uri, route_name, route_group_id)
                if not line:
                    continue
                if not self._is_ttc_line_enabled(line):
                    continue

                for stop_time in route.get("stop_times", []):
                    eta_minutes = self._ttc_eta_minutes(stop_time, now_ts)
                    if eta_minutes is None:
                        continue
                    if not self._is_in_arrival_window(eta_minutes):
                        continue

                    output.append(
                        {
                            "line": line,
                            "destination": self._ttc_destination_name(stop_time, route_name),
                            "mins": str(eta_minutes),
                            "eta": eta_minutes,
                        }
                    )

        return output

    def _replace_trains(self, trains, now):
        previous_trains = self.trains
        self.trains = trains

        if not self.trains:
            self.scroll_index = 0
        else:
            self.scroll_index %= len(self.trains)

        if self.trains != previous_trains:
            self.page_start_time = now

    def _normalize_wmata_mins(self, raw):
        text = str(raw or "").strip().upper()
        if text in {"BRD", "ARR"}:
            return "0"
        if not text:
            return "--"
        match = re.search(r"\d+", text)
        return match.group(0) if match else "--"

    def _arrival_window(self):
        min_minutes = self._safe_int(getattr(config, "METRO_MIN_ARRIVAL_MINUTES", 0), 0)
        max_minutes = self._safe_int(getattr(config, "METRO_MAX_ARRIVAL_MINUTES", 20), 20)

        min_minutes = max(0, min_minutes)
        max_minutes = max(0, max_minutes)
        if min_minutes > max_minutes:
            min_minutes, max_minutes = max_minutes, min_minutes
        return min_minutes, max_minutes

    def _is_in_arrival_window(self, minutes):
        min_minutes, max_minutes = self._arrival_window()
        return min_minutes <= int(minutes) <= max_minutes

    def _safe_int(self, value, fallback):
        try:
            return int(value)
        except Exception:
            return fallback

    def _parse_line_filter(self, raw):
        lines = set()
        for part in str(raw or "").split(","):
            token = self._normalize_nyc_route_id(part)
            if token:
                lines.add(token)
        return lines

    def _wmata_line_filter(self):
        return self._parse_line_filter(getattr(config, "WMATA_LINE_FILTER", ""))

    def _nyc_line_filter(self):
        return self._parse_line_filter(getattr(config, "NYC_LINE_FILTER", ""))

    def _ttc_line_filter(self):
        return self._parse_line_filter(getattr(config, "TTC_LINE_FILTER", ""))

    def _is_wmata_line_enabled(self, line):
        selected = self._wmata_line_filter()
        if not selected:
            return True
        return str(line or "").strip().upper() in selected

    def _is_nyc_line_enabled(self, route):
        selected = self._nyc_line_filter()
        if not selected:
            return True

        normalized_route = self._normalize_nyc_route_id(route)
        if normalized_route in selected:
            return True

        # Allow generic "S" filter to include shuttle feed variants like GS/FS.
        if normalized_route in {"GS", "FS"} and "S" in selected:
            return True

        return False

    def _is_ttc_line_enabled(self, line):
        selected = self._ttc_line_filter()
        if not selected:
            return True
        return str(line or "").strip().upper() in selected

    def _load_nyc_stop_name_map(self):
        path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web", "nyc_stations.json"))
        try:
            with open(path, "r", encoding="utf-8") as f:
                stations = json.load(f)
        except Exception:
            return {}

        mapping = {}
        if not isinstance(stations, list):
            return mapping

        for station in stations:
            if not isinstance(station, dict):
                continue

            name = str(station.get("name", "") or "").strip()
            if not name:
                continue

            stop_ids = station.get("stop_ids", [])
            if not isinstance(stop_ids, list):
                continue

            for raw_stop_id in stop_ids:
                stop_id = str(raw_stop_id or "").strip().upper()
                if not stop_id:
                    continue
                mapping[stop_id] = name
                mapping[self._strip_nyc_stop_id(stop_id)] = name

        return mapping

    def _wmata_station_codes(self):
        raw = str(getattr(config, "WMATA_STATION_CODE", "") or "")
        codes = []
        seen = set()
        for part in raw.replace("\n", ",").split(","):
            code = str(part or "").strip().upper()
            if not code or code in seen:
                continue
            seen.add(code)
            codes.append(code)
        return tuple(sorted(codes))

    def _nyc_stop_ids(self):
        raw = str(getattr(config, "NYC_STOP_IDS", "") or "")
        return {part.strip().upper() for part in raw.split(",") if part.strip()}

    def _nyc_feed_urls(self):
        raw = str(getattr(config, "NYC_MTA_FEED_URL", "") or "").replace("\n", ",")
        urls = []
        seen = set()
        for part in raw.split(","):
            url = part.strip()
            if not url or url in seen:
                continue
            seen.add(url)
            urls.append(url)
        return tuple(urls)

    def _ttc_station_id(self):
        return str(getattr(config, "TTC_STATION_ID", "") or "").strip().lower()

    def _ttc_stop_uris(self):
        raw = str(getattr(config, "TTC_STOP_URIS", "") or "")
        stop_uris = []
        seen = set()
        for part in raw.replace("\n", ",").split(","):
            uri = str(part or "").strip().lower()
            if not uri or uri in seen:
                continue
            seen.add(uri)
            stop_uris.append(uri)
        if stop_uris:
            return tuple(stop_uris)

        # Backward-compatible fallback: derive stop URIs from station metadata if config CSV is blank.
        station_id = self._ttc_station_id()
        if not station_id:
            return tuple()
        stations_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web", "ttc_stations.json"))
        try:
            with open(stations_path, "r", encoding="utf-8") as f:
                stations = json.load(f)
        except Exception:
            return tuple()
        for station in stations if isinstance(stations, list) else []:
            if not isinstance(station, dict):
                continue
            if str(station.get("id", "") or "").strip().lower() != station_id:
                continue
            for candidate in station.get("stop_uris", []):
                uri = str(candidate or "").strip().lower()
                if not uri or uri in seen:
                    continue
                seen.add(uri)
                stop_uris.append(uri)
        return tuple(stop_uris)

    def _normalize_nyc_route_id(self, route_id):
        route = str(route_id or "").strip().upper()
        if route == "7X":
            return "7"
        return route[:2]

    def _ttc_route_to_line(self, route_uri, route_name, route_group_id=""):
        group_id = str(route_group_id or "").strip()
        if group_id in {"1", "2", "3", "4"}:
            return group_id

        route_key = str(route_uri or "").strip().lower()
        if route_key in TTC_ROUTE_TO_LINE:
            return TTC_ROUTE_TO_LINE[route_key]
        if "line_1" in route_key or route_key.startswith("1_"):
            return "1"
        if "line_2" in route_key or route_key.startswith("2_"):
            return "2"
        if "line_3" in route_key or route_key.startswith("3_"):
            return "3"
        if "line_4" in route_key or route_key.startswith("4_"):
            return "4"

        name = str(route_name or "").strip().lower()
        line_match = re.search(r"\bline\s*([1-4])\b", name)
        if line_match:
            return line_match.group(1)
        if "sheppard" in name:
            return "4"
        if "bloor-danforth" in name:
            return "2"
        if "scarborough" in name:
            return "3"
        if "yonge-university" in name:
            return "1"
        return ""

    def _nyc_direction_label(self, stop_id):
        if stop_id.endswith("N"):
            return "Uptown"
        if stop_id.endswith("S"):
            return "Downtown"
        return "Train"

    def _strip_nyc_stop_id(self, stop_id):
        value = str(stop_id or "").strip().upper()
        if value.endswith("N") or value.endswith("S"):
            return value[:-1]
        return value

    def _nyc_terminal_stop_id(self, trip_update):
        for stop_update in reversed(trip_update.stop_time_update):
            stop_id = str(getattr(stop_update, "stop_id", "") or "").strip().upper()
            if stop_id:
                return stop_id
        return ""

    def _nyc_destination_name(self, route, trip_update, current_stop_id):
        terminal_stop_id = self._nyc_terminal_stop_id(trip_update)
        if terminal_stop_id:
            terminal_name = self._nyc_stop_name_map.get(terminal_stop_id)
            if not terminal_name:
                terminal_name = self._nyc_stop_name_map.get(self._strip_nyc_stop_id(terminal_stop_id))
            if terminal_name:
                return terminal_name

        direction = self._nyc_direction_label(current_stop_id)
        if direction == "Train":
            return route
        return f"{route} {direction}"

    def _ttc_destination_name(self, stop_time, route_name):
        shape = str(stop_time.get("shape", "") or "").strip()
        if " TO " in shape.upper():
            dest = re.split(r"\s+TO\s+", shape, maxsplit=1, flags=re.IGNORECASE)[-1].strip()
            if dest:
                return dest

        route = str(route_name or "").strip()
        return route or "Train"

    def _gtfs_eta_minutes(self, stop_update, now_ts):
        arrival = getattr(stop_update, "arrival", None)
        departure = getattr(stop_update, "departure", None)

        eta_ts = None
        if arrival and getattr(arrival, "time", 0):
            eta_ts = int(arrival.time)
        elif departure and getattr(departure, "time", 0):
            eta_ts = int(departure.time)

        if eta_ts is None:
            return None

        delta = eta_ts - now_ts
        if delta < -30:
            return None
        return max(0, int(round(delta / 60.0)))

    def _dedupe_nyc_arrivals(self, rows):
        # Keep unique trip/stop predictions first, then cap by arrival order.
        seen = set()
        output = []
        for row in rows:
            key = (row["trip_id"], row["stop_id"])
            if key in seen:
                continue
            seen.add(key)
            output.append(row)
        return output

    def _ttc_eta_minutes(self, stop_time, now_ts):
        dep_ts = stop_time.get("departure_timestamp")
        if dep_ts is None:
            return None
        try:
            eta_ts = int(dep_ts)
        except Exception:
            return None

        delta = eta_ts - now_ts
        if delta < -30:
            return None
        return max(0, int(round(delta / 60.0)))

    def _dedupe_ttc_arrivals(self, rows):
        seen = set()
        output = []
        for row in rows:
            key = (row["line"], row["destination"], row["eta"])
            if key in seen:
                continue
            seen.add(key)
            output.append(row)
        return output

    def _pair_for_index(self, start_index):
        if not self.trains:
            return []
        pair = [self.trains[start_index % len(self.trains)]]
        if len(self.trains) > 1:
            pair.append(self.trains[(start_index + 1) % len(self.trains)])
        return pair

    def _draw_train_row(self, draw, train, row_y, text_start_x, time_on_page):
        if row_y <= -16 or row_y >= self.height:
            return

        line = str(train.get("Line", "--")).upper()
        dest = train.get("Destination", "")
        mins = train.get("Min", "--")
        line_color = self._line_color(line)

        eta_width = self.font_tall.getlength(mins)
        mask_x_start = 64 - eta_width - 3
        visible_space = mask_x_start - text_start_x

        text_width = self.font_tall.getlength(dest)
        x_pos = text_start_x

        if text_width > visible_space:
            last_space = dest.rfind(" ")
            if last_space != -1:
                max_offset = self.font_tall.getlength(dest[: last_space + 1])
            else:
                max_offset = text_width - visible_space

            if time_on_page < 1.0:
                offset = 0
            else:
                active_scroll_time = time_on_page - 1.0
                offset = active_scroll_time * self.scroll_speed
                if offset > max_offset:
                    offset = max_offset

            x_pos = text_start_x - offset

        draw.text((x_pos, row_y + 3), dest, font=self.font_tall, fill=config.COLOR_BLUE)

        # Masks.
        draw.rectangle((0, row_y, 12, row_y + 16), fill=(0, 0, 0))
        draw.rectangle((mask_x_start, row_y, 64, row_y + 16), fill=(0, 0, 0))

        # Icons and time.
        self._draw_octagon(draw, 2, row_y + 3, line_color, line[:1] or "?")
        time_x = 64 - eta_width - 1
        draw.text((time_x, row_y + 3), mins, font=self.font_tall, fill=config.COLOR_WHITE)

    def draw(self):
        draw = ImageDraw.Draw(self.canvas)
        draw.rectangle((0, 0, self.width, self.height), fill=(0, 0, 0))

        if not self.trains:
            label = "NO TRAINS"
            if self._metro_system() == "nyc":
                label = "NYC NO DATA"
            if self._metro_system() == "ttc":
                label = "TTC NO DATA"
            draw.text((1, 12), label, font=self.font_small, fill=config.COLOR_GREY)
            return self.canvas

        # Trains list can shrink between fetches; keep index in range.
        self.scroll_index %= len(self.trains)

        # Determine which trains to show.
        current_pair = self._pair_for_index(self.scroll_index)

        # Calculate page duration.
        longest_scroll_time = 0
        text_start_x = 13

        for train in current_pair:
            eta_width = self.font_tall.getlength(train["Min"])
            visible_width = (64 - eta_width - 3) - text_start_x
            dest = train["Destination"]
            text_width = self.font_tall.getlength(dest)

            if text_width > visible_width:
                last_space = dest.rfind(" ")
                if last_space != -1:
                    prefix_width = self.font_tall.getlength(dest[: last_space + 1])
                    scroll_dist = prefix_width
                else:
                    scroll_dist = text_width - visible_width

                time_needed = scroll_dist / self.scroll_speed
                if time_needed > longest_scroll_time:
                    longest_scroll_time = time_needed

        page_duration = max(4.0, 1.0 + longest_scroll_time + 2.0)

        # Handle cycling.
        now = time.time()
        time_on_page = now - self.page_start_time
        transition_style = self._metro_page_transition()
        transition_duration = 0.35
        page_step = 2 if len(self.trains) > 1 else 1
        can_slide = transition_style == "slide" and len(self.trains) > page_step
        rows_to_draw = []

        if can_slide and time_on_page > page_duration:
            transition_elapsed = time_on_page - page_duration
            if transition_elapsed >= transition_duration:
                self.scroll_index = (self.scroll_index + page_step) % len(self.trains)
                self.page_start_time = now
                current_pair = self._pair_for_index(self.scroll_index)
                rows_to_draw = [
                    (current_pair[0], 0, 0.0),
                ]
                if len(current_pair) > 1:
                    rows_to_draw.append((current_pair[1], 16, 0.0))
            else:
                shift = int(round((transition_elapsed / transition_duration) * 32))
                next_pair = self._pair_for_index(self.scroll_index + page_step)
                if current_pair:
                    rows_to_draw.append((current_pair[0], -shift, page_duration))
                if len(current_pair) > 1:
                    rows_to_draw.append((current_pair[1], 16 - shift, page_duration))
                if next_pair:
                    rows_to_draw.append((next_pair[0], 32 - shift, 0.0))
                if len(next_pair) > 1:
                    rows_to_draw.append((next_pair[1], 48 - shift, 0.0))
        else:
            if time_on_page > page_duration:
                if len(self.trains) > page_step:
                    self.scroll_index = (self.scroll_index + page_step) % len(self.trains)
                self.page_start_time = now
                time_on_page = 0
                current_pair = self._pair_for_index(self.scroll_index)

            rows_to_draw = [
                (current_pair[0], 0, time_on_page),
            ]
            if len(current_pair) > 1:
                rows_to_draw.append((current_pair[1], 16, time_on_page))

        for train, row_y, row_time in rows_to_draw:
            self._draw_train_row(draw, train, row_y, text_start_x, row_time)

        return self.canvas

    def _line_color(self, line):
        line = str(line or "").upper()
        if self._metro_system() == "nyc":
            return NYC_LINE_COLORS.get(line) or NYC_LINE_COLORS.get(line[:1], config.COLOR_GREY)
        if self._metro_system() == "ttc":
            return TTC_LINE_COLORS.get(line) or TTC_LINE_COLORS.get(line[:1], config.COLOR_GREY)
        return WMATA_LINE_COLORS.get(line, config.COLOR_GREY)

    def _draw_bitmap_glyph(self, draw, x, y, pixels):
        min_x = min(px for px, _ in pixels)
        max_x = max(px for px, _ in pixels)
        min_y = min(py for _, py in pixels)
        max_y = max(py for _, py in pixels)

        glyph_w = (max_x - min_x) + 1
        glyph_h = (max_y - min_y) + 1

        start_x = x + ((9 - glyph_w) // 2) - min_x
        start_y = y + ((9 - glyph_h) // 2) - min_y

        # Optical centering: some glyphs (especially numeric routes) are
        # geometrically centered by bounds but still appear right-heavy.
        avg_x = sum(px for px, _ in pixels) / float(len(pixels))
        desired_center_x = x + 4
        current_center_x = start_x + avg_x
        start_x += int(round(desired_center_x - current_center_x))

        for px, py in pixels:
            draw.point((start_x + px, start_y + py), fill=(255, 255, 255))

    def _draw_octagon(self, draw, x, y, color, text):
        """Draw a 9x9 octagon with either bitmap letter or tiny fallback glyph."""
        points = [
            (x + 2, y),
            (x + 6, y),
            (x + 8, y + 2),
            (x + 8, y + 6),
            (x + 6, y + 8),
            (x + 2, y + 8),
            (x, y + 6),
            (x, y + 2),
        ]
        draw.polygon(points, outline=color, fill=color)

        glyph = (text or "?").upper()
        letter_pixels = BITMAP_LETTERS.get(glyph)
        if letter_pixels:
            self._draw_bitmap_glyph(draw, x, y, letter_pixels)
            return

        # NYC numeric routes render cleaner with a dedicated bitmap than the tiny fallback font.
        digit_pixels = BITMAP_DIGITS.get(glyph)
        if digit_pixels:
            self._draw_bitmap_glyph(draw, x, y, digit_pixels)
            return

        # Fallback for numeric/other route IDs not covered by bitmap map.
        if hasattr(self.font_small, "getbbox"):
            left, top, right, bottom = self.font_small.getbbox(glyph)
            tw = right - left
            th = bottom - top
            tx = x + max(0, (9 - tw) // 2) - left
            ty = y + max(0, (9 - th) // 2) - top
        else:
            tw = int(self.font_small.getlength(glyph))
            tx = x + max(1, (9 - tw) // 2)
            ty = y + 1
        draw.text((tx, ty), glyph, font=self.font_small, fill=(255, 255, 255))
