import importlib
import re
import time
from datetime import datetime

import requests
from PIL import Image, ImageDraw, ImageFont

import config
from core.widget import Widget


class SportsWidget(Widget):
    """NBA scoreboard with a team-first, high-legibility layout.

    64x32 layout:
      y 0-5   : game status (Q/clock/final)
      y 7-16  : away row (small color bar + team + score)
      y 18-27 : home row (small color bar + team + score)
      y 28-31 : timeout summary + optional game index
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
        self.color_dim = (146, 156, 176)
        self.color_loser = (98, 108, 126)
        self.color_possession = (255, 176, 72)
        self.color_cycle = (84, 96, 118)

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
        fetch_key = test_date or "today"
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
        return raw if re.fullmatch(r"\d{8}", raw) else ""

    def _get_view_mode(self):
        value = str(getattr(config, "SPORTS_VIEW_MODE", "all_live") or "all_live").lower()
        if value in {"favorites", "all_live", "all_teams"}:
            return value
        return "all_live"

    def _get_live_focus(self):
        return bool(getattr(config, "SPORTS_LIVE_FOCUS", True))

    def _get_favorites(self):
        raw = str(getattr(config, "SPORTS_FAVORITE_TEAMS", "") or "")
        return {abbr.strip().upper() for abbr in raw.split(",") if abbr.strip()}

    def _apply_view_filter(self):
        previous_id = self.games[self.current_game_index].get("id") if self.games else None
        view_mode = self._get_view_mode()

        if view_mode == "favorites":
            favorites = self._get_favorites()
            if favorites:
                base_games = [
                    g for g in self.all_games
                    if g["away"]["abbr"] in favorites or g["home"]["abbr"] in favorites
                ]
                self.placeholder_reason = "no fav games" if not base_games else None
            else:
                base_games = []
                self.placeholder_reason = "pick a team"
        else:
            base_games = list(self.all_games)
            self.placeholder_reason = "no games" if not base_games else None

        if self._get_live_focus():
            live_games = [g for g in base_games if g.get("state") == "in"]
            self.games = live_games if live_games else base_games
        else:
            self.games = base_games

        if not self.games and self.placeholder_reason is None:
            self.placeholder_reason = "no games"

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
        self._draw_status_row(draw, game)
        self._draw_team_row(draw, game, "away", 7)
        self._draw_team_row(draw, game, "home", 18)
        self._draw_timeout_row(draw, game)
        return self.canvas

    def _draw_placeholder(self, draw):
        label = "NBA"
        lw = int(self.font_tall.getlength(label))
        draw.text(((self.width - lw) // 2, 5), label, font=self.font_tall, fill=self.color_text)
        sub = self._fit_text(self.placeholder_reason or "no games", self.width - 4, self.font_small)
        sw = int(self.font_small.getlength(sub))
        draw.text(((self.width - sw) // 2, 19), sub, font=self.font_small, fill=self.color_dim)

    def _draw_status_row(self, draw, game):
        status = self._fit_text(self._status_text(game), self.width - 4, self.font_small)
        sw = int(self.font_small.getlength(status))
        draw.text(((self.width - sw) // 2, 0), status, font=self.font_small, fill=self.color_dim)

    def _draw_team_row(self, draw, game, side, y):
        team = game[side]
        other = game["home"] if side == "away" else game["away"]

        draw.rectangle((0, y + 1, self.BAR_WIDTH - 1, y + 8), fill=team["color"])

        team_color, score_color = self._team_row_colors(game, team, other)
        team_x = self.BAR_WIDTH + 2
        draw.text((team_x, y), team["abbr"], font=self.font_tall, fill=team_color)
        team_w = int(self.font_tall.getlength(team["abbr"]))

        if game.get("possession") == side:
            self._draw_possession_arrow(draw, team_x + team_w + 2, y + 2)

        score = str(team["score"])
        score_w = int(self.font_tall.getlength(score))
        draw.text((self.width - score_w - 1, y), score, font=self.font_tall, fill=score_color)

    def _team_row_colors(self, game, team, other):
        if game.get("state") != "post":
            return self.color_text, self.color_text

        if team["score"] > other["score"]:
            return self.color_text, self.color_text
        if team["score"] < other["score"]:
            return self.color_loser, self.color_loser
        return self.color_text, self.color_text

    def _draw_possession_arrow(self, draw, x, y):
        draw.polygon([(x, y), (x, y + 4), (x + 2, y + 2)], fill=self.color_possession)

    def _draw_timeout_row(self, draw, game):
        away_to = game["away"].get("timeouts")
        home_to = game["home"].get("timeouts")

        if away_to is not None or home_to is not None:
            a = "-" if away_to is None else str(max(0, min(7, away_to)))
            h = "-" if home_to is None else str(max(0, min(7, home_to)))
            text = f"TO {a}-{h}"
            tw = int(self.font_small.getlength(text))
            draw.text(((self.width - tw) // 2, 28), text, font=self.font_small, fill=self.color_dim)

        if len(self.games) > 1:
            cycle = f"{self.current_game_index + 1}/{len(self.games)}"
            cw = int(self.font_small.getlength(cycle))
            draw.text((self.width - cw - 1, 28), cycle, font=self.font_small, fill=self.color_cycle)

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
        abbr = (
            team.get("abbreviation")
            or team.get("shortDisplayName")
            or team.get("displayName")
            or "---"
        ).upper()
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
        raw = situation.get("possession") or situation.get("teamInPossession")
        if isinstance(raw, dict):
            raw = raw.get("id") or raw.get("teamId")
        if raw is None:
            return None

        raw_str = str(raw).lower()
        if raw_str in {"home", "away"}:
            return raw_str

        home_ids = {str(home.get("id", "")), str((home.get("team") or {}).get("id", ""))}
        away_ids = {str(away.get("id", "")), str((away.get("team") or {}).get("id", ""))}
        if str(raw) in home_ids:
            return "home"
        if str(raw) in away_ids:
            return "away"
        return None

    # ----------------------------------------------------------------- helpers

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
