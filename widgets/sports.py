import importlib
import re
import time
from datetime import datetime

import requests
from PIL import Image, ImageDraw, ImageFont

import config
from core.widget import Widget


class SportsWidget(Widget):
    """NBA scoreboard, score-hero layout with team-colored side bars.

    Layout (64x32):
      cols 0-1   : away color bar, full height
      cols 62-63 : home color bar, full height
      y 0-5      : away/home abbreviations + possession arrow (4x6 font)
      y 7-16     : score, centered, 6x10 font (the hero)
      y 19-24    : period + clock or final/tipoff text (4x6 font)
      y 27-28    : timeout dots, 7 per side (live games only)
    """

    SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

    BAR_WIDTH = 2

    def __init__(self, width, height):
        super().__init__(width, height)
        self.all_games = []
        self.games = []
        self.current_game_index = 0
        self.last_fetch = 0.0
        self.last_fetch_key = None
        self.last_rotate = time.time()
        self.fetch_interval = 20
        self.rotate_interval = 8
        self.placeholder_reason = "loading"

        self.color_text = (244, 246, 252)
        self.color_dim = (140, 150, 168)
        self.color_loser = (96, 104, 122)
        self.color_dash = (90, 102, 124)
        self.color_possession = (255, 168, 56)
        self.color_timeout_on = (220, 224, 232)
        self.color_timeout_off = (40, 46, 58)

        try:
            self.font_tall = ImageFont.truetype(config.FONT_PATH_TALL, 10)
        except Exception:
            self.font_tall = ImageFont.load_default()

        try:
            self.font_small = ImageFont.truetype(config.FONT_PATH_SMALL, 6)
        except Exception:
            self.font_small = ImageFont.load_default()

    # ------------------------------------------------------------------ update

    def update(self):
        now = time.time()
        importlib.reload(config)

        test_date = self._get_test_date()
        fetch_key = test_date or "live"
        if fetch_key != self.last_fetch_key or now - self.last_fetch >= self.fetch_interval:
            self._fetch_games(test_date)
            self.last_fetch = now
            self.last_fetch_key = fetch_key

        self._apply_view_filter()

        if len(self.games) > 1 and now - self.last_rotate >= self.rotate_interval:
            self.current_game_index = (self.current_game_index + 1) % len(self.games)
            self.last_rotate = now

    def _get_test_date(self):
        raw = str(getattr(config, "SPORTS_TEST_DATE", "") or "").strip()
        if re.fullmatch(r"\d{8}", raw):
            return raw
        return ""

    def _get_view_mode(self):
        return str(getattr(config, "SPORTS_VIEW_MODE", "all_live") or "all_live").lower()

    def _get_favorites(self):
        raw = str(getattr(config, "SPORTS_FAVORITE_TEAMS", "") or "")
        return {a.strip().upper() for a in raw.split(",") if a.strip()}

    def _apply_view_filter(self):
        previous_id = self.games[self.current_game_index].get("id") if self.games else None

        if self._get_view_mode() == "favorites":
            favorites = self._get_favorites()
            if favorites:
                filtered = [
                    g for g in self.all_games
                    if g["away"]["abbr"] in favorites or g["home"]["abbr"] in favorites
                ]
                self.games = filtered
                self.placeholder_reason = "no fav games" if not filtered else None
            else:
                self.games = []
                self.placeholder_reason = "pick a team"
        else:
            self.games = list(self.all_games)
            self.placeholder_reason = None if self.games else "no games"

        if previous_id:
            for idx, game in enumerate(self.games):
                if game.get("id") == previous_id:
                    self.current_game_index = idx
                    return
        self.current_game_index = 0

    # -------------------------------------------------------------------- draw

    def draw(self):
        self.canvas = Image.new("RGB", (self.width, self.height), (0, 0, 0))
        draw = ImageDraw.Draw(self.canvas)

        if not self.games:
            self._draw_placeholder(draw)
            return self.canvas

        game = self.games[self.current_game_index]
        self._draw_team_bars(draw, game)
        self._draw_abbrev_row(draw, game)
        self._draw_score_row(draw, game)
        self._draw_status_row(draw, game)
        self._draw_timeouts_row(draw, game)
        return self.canvas

    def _draw_placeholder(self, draw):
        text = "NBA"
        tw = int(self.font_tall.getlength(text))
        draw.text(((self.width - tw) // 2, 5), text, font=self.font_tall, fill=self.color_text)
        sub = self.placeholder_reason or "no games"
        sub = self._fit_text(sub, self.width - 4, self.font_small)
        sw = int(self.font_small.getlength(sub))
        draw.text(((self.width - sw) // 2, 19), sub, font=self.font_small, fill=self.color_dim)

    def _draw_team_bars(self, draw, game):
        away_color = game["away"]["color"]
        home_color = game["home"]["color"]
        draw.rectangle((0, 0, self.BAR_WIDTH - 1, self.height - 1), fill=away_color)
        draw.rectangle((self.width - self.BAR_WIDTH, 0, self.width - 1, self.height - 1), fill=home_color)

    def _draw_abbrev_row(self, draw, game):
        away_abbr = game["away"]["abbr"]
        home_abbr = game["home"]["abbr"]
        possession = game["possession"]

        y = 0
        ax = self.BAR_WIDTH + 2
        draw.text((ax, y), away_abbr, font=self.font_small, fill=self.color_text)
        aw = int(self.font_small.getlength(away_abbr))

        hw = int(self.font_small.getlength(home_abbr))
        hx = self.width - self.BAR_WIDTH - 2 - hw
        draw.text((hx, y), home_abbr, font=self.font_small, fill=self.color_text)

        if possession == "away":
            self._draw_possession_arrow(draw, ax + aw + 2, 1, "right")
        elif possession == "home":
            self._draw_possession_arrow(draw, hx - 5, 1, "left")

    def _draw_possession_arrow(self, draw, x, y, direction):
        if direction == "right":
            draw.polygon([(x, y), (x, y + 4), (x + 2, y + 2)], fill=self.color_possession)
        else:
            draw.polygon([(x + 2, y), (x + 2, y + 4), (x, y + 2)], fill=self.color_possession)

    def _draw_score_row(self, draw, game):
        away_score = str(game["away"]["score"])
        home_score = str(game["home"]["score"])

        away_w = int(self.font_tall.getlength(away_score))
        home_w = int(self.font_tall.getlength(home_score))
        dash_w = 5
        gap = 3
        total_w = away_w + gap + dash_w + gap + home_w

        y = 7
        x_start = (self.width - total_w) // 2

        away_color, home_color = self._score_colors(game)

        x = x_start
        draw.text((x, y), away_score, font=self.font_tall, fill=away_color)
        x += away_w + gap
        dash_y = y + 5
        draw.line((x, dash_y, x + dash_w - 1, dash_y), fill=self.color_dash)
        x += dash_w + gap
        draw.text((x, y), home_score, font=self.font_tall, fill=home_color)

    def _score_colors(self, game):
        # Only dim the loser at FINAL — during live games both teams stay bright.
        if game.get("state") == "post":
            a, h = game["away"]["score"], game["home"]["score"]
            if a > h:
                return self.color_text, self.color_loser
            if h > a:
                return self.color_loser, self.color_text
        return self.color_text, self.color_text

    def _draw_status_row(self, draw, game):
        text = self._status_text(game)
        max_w = self.width - 2 * self.BAR_WIDTH - 4
        text = self._fit_text(text, max_w, self.font_small)
        tw = int(self.font_small.getlength(text))
        x = (self.width - tw) // 2
        draw.text((x, 19), text, font=self.font_small, fill=self.color_dim)

    def _draw_timeouts_row(self, draw, game):
        if game.get("state") != "in":
            return

        away_to = game["away"].get("timeouts")
        home_to = game["home"].get("timeouts")
        if away_to is None and home_to is None:
            return

        y = 27
        spacing = 3  # 2px dot + 1px gap
        block_w = 7 * spacing - 1  # last gap not counted = 20

        if away_to is not None:
            ax = self.BAR_WIDTH + 2
            self._draw_dot_row(draw, ax, y, away_to, spacing)

        if home_to is not None:
            hx = self.width - self.BAR_WIDTH - 2 - block_w
            self._draw_dot_row(draw, hx, y, home_to, spacing)

    def _draw_dot_row(self, draw, x_start, y, count, spacing):
        for i in range(7):
            color = self.color_timeout_on if i < count else self.color_timeout_off
            x = x_start + i * spacing
            draw.point((x, y), fill=color)
            draw.point((x + 1, y), fill=color)
            draw.point((x, y + 1), fill=color)
            draw.point((x + 1, y + 1), fill=color)

    # ----------------------------------------------------------------- fetching

    def _fetch_games(self, test_date=""):
        url = f"{self.SCOREBOARD_URL}?dates={test_date}" if test_date else self.SCOREBOARD_URL
        try:
            response = requests.get(url, timeout=8)
            if response.status_code != 200:
                return
            payload = response.json()
        except Exception as exc:
            print(f"Sports API error: {exc}")
            return

        parsed = []
        for event in payload.get("events", []):
            game = self._parse_event(event)
            if game:
                parsed.append(game)

        parsed.sort(key=self._sort_key)
        self.all_games = parsed

    def _parse_event(self, event):
        competitions = event.get("competitions") or []
        if not competitions:
            return None
        competition = competitions[0]
        competitors = competition.get("competitors") or []
        if len(competitors) < 2:
            return None

        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if not home or not away:
            away, home = competitors[0], competitors[1]

        status = event.get("status") or competition.get("status") or {}
        status_type = status.get("type") or {}
        state = str(status_type.get("state", "pre")).lower()
        if state not in {"pre", "in", "post"}:
            state = "pre"

        return {
            "id": str(event.get("id", "")),
            "state": state,
            "period": self._as_int(status.get("period"), 0),
            "clock": status.get("displayClock") or "",
            "detail": status_type.get("shortDetail")
            or status_type.get("detail")
            or status_type.get("description")
            or "",
            "date_ts": self._parse_timestamp(event.get("date")),
            "possession": self._detect_possession(competition, home, away),
            "away": self._parse_team(away, default_color=(120, 168, 240)),
            "home": self._parse_team(home, default_color=(240, 120, 120)),
        }

    def _parse_team(self, competitor, default_color):
        team = competitor.get("team") or {}
        abbr = (team.get("abbreviation") or team.get("shortDisplayName") or team.get("displayName") or "---").upper()
        abbr = "".join(ch for ch in abbr if ch.isalnum())[:3] or "---"
        return {
            "abbr": abbr,
            "score": self._as_int(competitor.get("score"), 0),
            "timeouts": self._extract_timeouts(competitor),
            "color": self._parse_team_color(team.get("color"), default_color),
            "id": str(competitor.get("id") or team.get("id") or ""),
        }

    def _extract_timeouts(self, competitor):
        candidates = [competitor.get("timeouts"), competitor.get("timeoutsRemaining")]
        stats = competitor.get("statistics")
        if isinstance(stats, list):
            for stat in stats:
                name = (stat.get("name") or stat.get("displayName") or "").lower()
                if "timeout" in name:
                    candidates.append(stat.get("value"))

        for candidate in candidates:
            value = self._as_int(candidate, None)
            if value is not None and 0 <= value <= 7:
                return value
        return None

    def _detect_possession(self, competition, home, away):
        for side, team in (("home", home), ("away", away)):
            raw = team.get("possession")
            if isinstance(raw, bool) and raw:
                return side
            if str(raw).lower() in {"true", "1", "yes"}:
                return side

        situation = competition.get("situation") or {}
        raw_possession = situation.get("possession") or situation.get("teamInPossession")
        if isinstance(raw_possession, dict):
            raw_possession = raw_possession.get("id") or raw_possession.get("teamId")
        if raw_possession is None:
            return None

        raw_str = str(raw_possession).lower()
        if raw_str in {"home", "away"}:
            return raw_str

        home_ids = {str(home.get("id", "")), str((home.get("team") or {}).get("id", ""))}
        away_ids = {str(away.get("id", "")), str((away.get("team") or {}).get("id", ""))}
        if str(raw_possession) in home_ids:
            return "home"
        if str(raw_possession) in away_ids:
            return "away"
        return None

    def _status_text(self, game):
        state = game.get("state")
        detail = str(game.get("detail", "")).upper()

        if state == "in":
            if "HALFTIME" in detail:
                return "HALFTIME"
            if "END OF" in detail:
                return detail
            clock = game.get("clock") or "--:--"
            return f"{self._period_label(game.get('period', 0))} {clock}"

        if state == "post":
            return detail if "FINAL" in detail else "FINAL"

        return detail or "TIPOFF SOON"

    def _period_label(self, period):
        p = self._as_int(period, 0)
        if p <= 0:
            return "Q1"
        if p <= 4:
            return f"Q{p}"
        ot = p - 4
        return "OT" if ot == 1 else f"{ot}OT"

    def _sort_key(self, game):
        state_order = {"in": 0, "pre": 1, "post": 2}.get(game.get("state"), 3)
        ts = game.get("date_ts", 0.0)
        if state_order == 2:
            return (state_order, -ts)
        return (state_order, ts)

    def _fit_text(self, text, max_width, font):
        if not text:
            return ""
        text = str(text)
        if int(font.getlength(text)) <= max_width:
            return text
        while text and int(font.getlength(text + "...")) > max_width:
            text = text[:-1]
        return (text + "...") if text else ""

    def _parse_team_color(self, color_hex, fallback):
        if not color_hex:
            return fallback
        raw = str(color_hex).strip().lstrip("#")
        if len(raw) != 6:
            return fallback
        try:
            r = int(raw[0:2], 16)
            g = int(raw[2:4], 16)
            b = int(raw[4:6], 16)
        except ValueError:
            return fallback
        # Bump very dark team colors so the side bars don't disappear on black.
        if (r + g + b) < 150:
            r = min(255, r + 60)
            g = min(255, g + 60)
            b = min(255, b + 60)
        return (r, g, b)

    def _parse_timestamp(self, iso_time):
        if not iso_time:
            return 0.0
        try:
            return datetime.fromisoformat(str(iso_time).replace("Z", "+00:00")).timestamp()
        except Exception:
            return 0.0

    def _as_int(self, value, default):
        try:
            return int(value)
        except Exception:
            return default
