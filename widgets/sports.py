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
      y 0-9   : game status (Q/clock/final) in larger text
      y 11-20 : away row (small color bar + team + score)
      y 22-31 : home row (small color bar + team + score)
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
        self.live_fetch_interval = 2
        self.idle_fetch_interval = 20
        self.rotate_interval = 8
        self.halftime_cycle_interval = 4
        self.placeholder_reason = "loading"
        self.possession_cache = {}
        self.halftime_categories = [
            ("points", "PTS"),
            ("rebounds", "REB"),
            ("assists", "AST"),
            ("steals", "STL"),
            ("blocks", "BLK"),
            ("rating", "RTG"),
        ]

        self.color_text = (244, 246, 252)
        self.color_dim = (196, 208, 230)
        self.color_loser = (98, 108, 126)
        self.color_possession = (255, 176, 72)

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
        poll_interval = self._current_fetch_interval()
        if fetch_key != self.last_fetch_key or now - self.last_fetch >= poll_interval:
            self._fetch_games(test_date)
            self.last_fetch = now
            self.last_fetch_key = fetch_key

        self._apply_view_filter()

        if len(self.games) > 1 and now - self.last_rotate >= self.rotate_interval:
            self.current_game_index = (self.current_game_index + 1) % len(self.games)
            self.last_rotate = now

    def _current_fetch_interval(self):
        # ESPN scoreboard returns the whole slate in one response,
        # so faster polling is still a single request, not one per game.
        watched_games = self.games if self.games else self.all_games
        has_live = any(g.get("state") == "in" for g in watched_games)
        return self.live_fetch_interval if has_live else self.idle_fetch_interval

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
        if self._is_halftime(game) and self._draw_halftime_stats(draw, game):
            return self.canvas

        self._draw_status_row(draw, game)
        self._draw_team_row(draw, game, "away", 11)
        self._draw_team_row(draw, game, "home", 22)
        return self.canvas

    def _draw_placeholder(self, draw):
        label = "NBA"
        lw = int(self.font_tall.getlength(label))
        draw.text(((self.width - lw) // 2, 5), label, font=self.font_tall, fill=self.color_text)
        sub = self._fit_text(self.placeholder_reason or "no games", self.width - 4, self.font_small)
        sw = int(self.font_small.getlength(sub))
        draw.text(((self.width - sw) // 2, 19), sub, font=self.font_small, fill=self.color_dim)

    def _draw_status_row(self, draw, game):
        if self._draw_live_status_row(draw, game):
            return

        status = self._fit_text(self._status_text(game), self.width - 2, self.font_tall)
        sw = int(self.font_tall.getlength(status))
        draw.text(((self.width - sw) // 2, 0), status, font=self.font_tall, fill=self.color_dim)

    def _draw_live_status_row(self, draw, game):
        # Custom render for live clock so ':' uses 1px dots instead of the font glyph.
        if game.get("state") != "in":
            return False

        detail = str(game.get("detail", "")).upper()
        if "HALFTIME" in detail or "END OF" in detail:
            return False

        clock = str(game.get("clock") or "")
        if ":" not in clock:
            return False
        mins, secs = clock.split(":", 1)
        if not mins or not secs:
            return False

        period_text = f"{self._period_label(game.get('period', 0))} "
        period_w = int(self.font_tall.getlength(period_text))
        mins_w = int(self.font_tall.getlength(mins))
        secs_w = int(self.font_tall.getlength(secs))

        gap_left = 0
        gap_right = 1
        total_w = period_w + mins_w + gap_left + 1 + gap_right + secs_w
        x = max(0, (self.width - total_w) // 2)
        y = 0

        draw.text((x, y), period_text, font=self.font_tall, fill=self.color_dim)
        x += period_w

        draw.text((x, y), mins, font=self.font_tall, fill=self.color_dim)
        x += mins_w + gap_left

        draw.point((x, y + 3), fill=self.color_dim)
        draw.point((x, y + 7), fill=self.color_dim)
        x += 1 + gap_right

        draw.text((x, y), secs, font=self.font_tall, fill=self.color_dim)
        return True

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

    def _draw_halftime_stats(self, draw, game):
        cards = self._build_halftime_cards(game)
        if not cards:
            return False

        self._draw_status_row(draw, game)

        card_index = int(time.time() / self.halftime_cycle_interval) % len(cards)
        card = cards[card_index]

        label = f"{card['label']} LEADERS"
        label = self._fit_text(label, self.width - 2, self.font_small)
        label_w = int(self.font_small.getlength(label))
        draw.text(((self.width - label_w) // 2, 11), label, font=self.font_small, fill=self.color_dim)

        self._draw_halftime_team_row(game["away"], card["away"], 18, draw)
        self._draw_halftime_team_row(game["home"], card["home"], 25, draw)
        return True

    def _draw_halftime_team_row(self, team, leaders, y, draw):
        draw.rectangle((0, y, self.BAR_WIDTH - 1, y + 5), fill=team["color"])

        parts = [team["abbr"]]
        if leaders:
            for leader in leaders[:2]:
                parts.append(f"{leader['tag']}{leader['val']}")
        else:
            parts.append("--")

        text = " ".join(parts)
        text = self._fit_text(text, self.width - self.BAR_WIDTH - 3, self.font_small)
        draw.text((self.BAR_WIDTH + 2, y), text, font=self.font_small, fill=self.color_text)

    def _build_halftime_cards(self, game):
        away_leaders = game["away"].get("leaders", {})
        home_leaders = game["home"].get("leaders", {})
        cards = []

        for key, label in self.halftime_categories:
            away_entries = away_leaders.get(key) or []
            home_entries = home_leaders.get(key) or []
            if away_entries or home_entries:
                cards.append({
                    "key": key,
                    "label": label,
                    "away": away_entries,
                    "home": home_entries,
                })

        if cards:
            return cards

        # Fallback: use any available categories if ESPN naming differs.
        seen = set()
        for key in list(away_leaders.keys()) + list(home_leaders.keys()):
            if key in seen:
                continue
            seen.add(key)
            cards.append({
                "key": key,
                "label": key[:3].upper(),
                "away": away_leaders.get(key) or [],
                "home": home_leaders.get(key) or [],
            })
        return cards

    def _team_row_colors(self, game, team, other):
        if game.get("state") != "post":
            return self.color_text, self.color_text

        if team["score"] > other["score"]:
            return self.color_text, self.color_text
        if team["score"] < other["score"]:
            return self.color_loser, self.color_loser
        return self.color_text, self.color_text

    def _draw_possession_arrow(self, draw, x, y):
        # Larger 4x6 triangle; points LEFT so it points back toward the team label.
        draw.polygon([(x + 3, y), (x + 3, y + 6), (x, y + 3)], fill=self.color_possession)

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
            "leaders": self._extract_team_leaders(competitor),
            "color": self._parse_team_color(team.get("color"), default_color),
            "id": str(competitor.get("id") or team.get("id") or ""),
        }

    def _extract_team_leaders(self, competitor):
        output = {}
        for leader_group in competitor.get("leaders") or []:
            cat_key = self._normalize_leader_category(
                leader_group.get("name")
                or leader_group.get("abbreviation")
                or leader_group.get("shortDisplayName")
                or ""
            )
            if not cat_key:
                continue

            entries = []
            for item in (leader_group.get("leaders") or [])[:2]:
                athlete = item.get("athlete") or {}
                tag = self._short_player_tag(
                    athlete.get("shortName")
                    or athlete.get("displayName")
                    or athlete.get("fullName")
                    or ""
                )
                val = self._short_leader_value(item.get("displayValue") or item.get("value"))
                if tag or val:
                    entries.append({"tag": tag or "?", "val": val or "--"})

            if entries:
                output[cat_key] = entries
        return output

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
        home_abbr = str((home.get("team") or {}).get("abbreviation") or "").upper()
        away_abbr = str((away.get("team") or {}).get("abbreviation") or "").upper()

        for side, team in (("home", home), ("away", away)):
            raw = (
                team.get("possession")
                or team.get("isPossession")
                or team.get("hasPossession")
                or team.get("onOffense")
                or (team.get("team") or {}).get("possession")
            )
            if isinstance(raw, bool) and raw:
                return side
            if str(raw).lower() in {"true", "1", "yes"}:
                return side

        situation = competition.get("situation") or {}
        raw = (
            situation.get("possession")
            or situation.get("teamInPossession")
            or situation.get("onOffense")
        )
        if isinstance(raw, dict):
            raw = (
                raw.get("id")
                or raw.get("teamId")
                or raw.get("abbreviation")
                or raw.get("homeAway")
            )
        if raw is None:
            last_play = situation.get("lastPlay")
            if isinstance(last_play, dict):
                last_team = last_play.get("team")
                if isinstance(last_team, dict):
                    raw = last_team.get("id") or last_team.get("abbreviation") or last_team.get("teamId")

        if raw is None:
            return self.possession_cache.get(str(competition.get("id", "")))

        raw_str = str(raw).lower()
        if raw_str in {"home", "away"}:
            self.possession_cache[str(competition.get("id", ""))] = raw_str
            return raw_str
        if raw_str == home_abbr.lower():
            self.possession_cache[str(competition.get("id", ""))] = "home"
            return "home"
        if raw_str == away_abbr.lower():
            self.possession_cache[str(competition.get("id", ""))] = "away"
            return "away"

        home_ids = {str(home.get("id", "")), str((home.get("team") or {}).get("id", ""))}
        away_ids = {str(away.get("id", "")), str((away.get("team") or {}).get("id", ""))}
        if str(raw) in home_ids:
            self.possession_cache[str(competition.get("id", ""))] = "home"
            return "home"
        if str(raw) in away_ids:
            self.possession_cache[str(competition.get("id", ""))] = "away"
            return "away"
        return self.possession_cache.get(str(competition.get("id", "")))

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

    def _is_halftime(self, game):
        detail = str(game.get("detail", "")).upper()
        return "HALFTIME" in detail or detail.startswith("HALF ")

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

    def _normalize_leader_category(self, raw):
        name = str(raw or "").strip().lower()
        if not name:
            return ""
        aliases = {
            "pts": "points",
            "point": "points",
            "points": "points",
            "reb": "rebounds",
            "rebound": "rebounds",
            "rebounds": "rebounds",
            "ast": "assists",
            "assist": "assists",
            "assists": "assists",
            "stl": "steals",
            "steal": "steals",
            "steals": "steals",
            "blk": "blocks",
            "block": "blocks",
            "blocks": "blocks",
            "rtg": "rating",
            "rating": "rating",
        }
        return aliases.get(name, name)

    def _short_player_tag(self, name):
        cleaned = re.sub(r"[^A-Za-z ]", " ", str(name or ""))
        parts = [p for p in cleaned.split() if p]
        if not parts:
            return ""
        base = parts[-1] if len(parts) > 1 else parts[0]
        return base[:3].upper()

    def _short_leader_value(self, value):
        text = str(value or "").strip()
        if not text:
            return ""
        match = re.search(r"\d+(?:\.\d+)?", text)
        if not match:
            return text[:2]
        num = match.group(0)
        if "." in num:
            num = num.split(".", 1)[0]
        return num[:2]

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
