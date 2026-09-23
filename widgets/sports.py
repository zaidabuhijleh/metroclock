import re
import threading
import time
from datetime import datetime, timedelta

import requests
from PIL import Image, ImageDraw, ImageFont

import config
import config_manager
from core.widget import Widget


ESPN_SITE = "https://site.api.espn.com/apis/site/v2/sports"


class SportsWidget(Widget):
    """Multi-league scoreboard, one game at a time.

    64x32 layout, the same grid in every state:
      y 0-8   : status row (clock / inning + bases / kickoff / FINAL)
      y 11-19 : away row  (2px colour bar, team, middle strip, score)
      y 22-30 : home row

    Before a game, the strip between team and score carries each record.
    """

    # "favorites": False means the league is a tournament slate with no team
    # picker; in My Teams view its whole day is shown.
    LEAGUES = {
        "nba": {"label": "NBA", "short": "NBA", "sport": "basketball", "path": "basketball/nba", "favorites": True},
        "wnba": {"label": "WNBA", "short": "WNBA", "sport": "basketball", "path": "basketball/wnba", "favorites": True},
        "nfl": {"label": "NFL", "short": "NFL", "sport": "football", "path": "football/nfl", "favorites": True},
        "mlb": {"label": "MLB", "short": "MLB", "sport": "baseball", "path": "baseball/mlb", "favorites": True},
        "nhl": {"label": "NHL", "short": "NHL", "sport": "hockey", "path": "hockey/nhl", "favorites": True},
        "usa.1": {"label": "MLS", "short": "MLS", "sport": "soccer", "path": "soccer/usa.1", "favorites": True},
        "eng.1": {"label": "Premier League", "short": "EPL", "sport": "soccer", "path": "soccer/eng.1", "favorites": True},
        "esp.1": {"label": "La Liga", "short": "LIGA", "sport": "soccer", "path": "soccer/esp.1", "favorites": True},
        "uefa.champions": {"label": "Champions League", "short": "UCL", "sport": "soccer", "path": "soccer/uefa.champions", "favorites": True},
        "fifa.world": {"label": "World Cup", "short": "WC", "sport": "soccer", "path": "soccer/fifa.world", "favorites": False},
        # College. A full-day scoreboard is 1-2 MB (hundreds of schools), far
        # too much to poll from a Pi Zero, so followed schools are fetched one
        # team at a time ("per_team"). Schools are keyed by ESPN team id:
        # abbreviations repeat (two OSUs).
        "college-football": {"label": "College Football", "short": "CFB", "sport": "football", "path": "football/college-football", "favorites": True, "per_team": True},
        "mens-college-basketball": {"label": "Men's College Basketball", "short": "NCAAM", "sport": "basketball", "path": "basketball/mens-college-basketball", "favorites": True, "per_team": True, "halves": True},
        "womens-college-basketball": {"label": "Women's College Basketball", "short": "NCAAW", "sport": "basketball", "path": "basketball/womens-college-basketball", "favorites": True, "per_team": True},
    }

    # Older app and web builds shipped their own team lists, and several of
    # their abbreviations are not the ones ESPN uses. A favourite saved as
    # "WAS" never matched the Wizards ("WSH"), so it silently showed nothing.
    LEGACY_ABBR_ALIASES = {
        "nba": {"GSW": "GS", "NOP": "NO", "NYK": "NY", "SAS": "SA", "UTA": "UTAH", "WAS": "WSH"},
        "eng.1": {"MCI": "MNC", "MUN": "MAN"},
    }

    BAR_WIDTH = 2
    AWAY_Y = 11
    HOME_Y = 22

    # Poll pacing, per league. ESPN returns a league's whole day in one
    # response (an MLB day is ~300 KB), so the fast rate is kept for the
    # leagues whose live games are actually on screen.
    POLL_LIVE_SHOWN = 4
    POLL_LIVE_OTHER = 20
    POLL_STARTING_SOON = 30
    POLL_IDLE = 120
    TEAM_INDEX_TTL = 24 * 3600
    SCHEDULE_TTL = 3 * 3600
    # With no games today, the panel rotates your teams' upcoming games:
    # everything in the next week, or at least each team's next game.
    UPCOMING_WINDOW = 7 * 24 * 3600
    UPCOMING_PER_TEAM = 4
    UPCOMING_MAX = 12

    STATUS_HOLD_SECONDS = 4
    LEADER_HOLD_SECONDS = 3
    SCORE_FLASH_SECONDS = 6

    def __init__(self, width, height):
        super().__init__(width, height)
        self.all_games = []
        self.games = []
        self.current_game_index = 0
        self.last_rotate = time.time()
        self.rotate_interval = 8
        self.placeholder_reason = "loading"

        self.color_text = (244, 246, 252)
        self.color_dim = (150, 162, 186)
        self.color_faint = (70, 78, 94)
        self.color_loser = (98, 108, 126)
        self.color_accent = (255, 176, 72)
        self.color_neutral_team = (120, 132, 156)

        try:
            self.font_tall = ImageFont.truetype(config.FONT_PATH_TALL, config.FONT_SIZE_TALL)
        except Exception:
            self.font_tall = ImageFont.load_default()
        try:
            self.font_small = ImageFont.truetype(config.FONT_PATH_SMALL, config.FONT_SIZE_SMALL)
        except Exception:
            self.font_small = ImageFont.load_default()

        # Per-league state, owned by the worker. The render thread only reads
        # the merged all_games list, which the worker rebinds whole.
        self._league_games = {}
        self._next_fetch_at = {}
        self._failure_delay = {}
        self._team_index = {}
        self._team_index_at = {}
        self._schedule_cache = {}
        self._slate_generation = 0
        self._seen_generation = -1
        self._score_memory = {}
        self._flash = {}
        self._fetch_failed = set()
        self._color_cache = {}

        self._fetch_signature = None
        self._fetch_wake = threading.Event()
        self._session = requests.Session()
        self._worker = threading.Thread(target=self._fetch_worker, name="sports-fetch", daemon=True)
        self._worker.start()

    # ================================================================ settings

    def _get_test_date(self):
        raw = str(getattr(config, "SPORTS_TEST_DATE", "") or "").strip()
        return raw if re.fullmatch(r"\d{8}", raw) else ""

    def _today_key(self):
        return datetime.now().strftime("%Y%m%d")

    def _get_league_keys(self):
        """Selected leagues, in the order the person picked them.

        SPORTS_LEAGUES is the multi-league list; SPORTS_LEAGUE is the older
        single choice and is still honoured when the list is empty.
        """
        raw = str(getattr(config, "SPORTS_LEAGUES", "") or "")
        keys = []
        for part in raw.split(","):
            key = part.strip().lower()
            if key in self.LEAGUES and key not in keys:
                keys.append(key)
        if keys:
            return keys
        single = str(getattr(config, "SPORTS_LEAGUE", "nba") or "nba").strip().lower()
        return [single if single in self.LEAGUES else "nba"]

    def _get_league_key(self):
        """Primary league. Kept for callers that predate multi-league."""
        return self._get_league_keys()[0]

    def _get_league(self):
        return self.LEAGUES[self._get_league_key()]

    def _get_view_mode(self):
        value = str(getattr(config, "SPORTS_VIEW_MODE", "all_live") or "all_live").lower()
        if value == "favorites":
            return "favorites"
        return "all_live"

    def _get_live_focus(self):
        return bool(getattr(config, "SPORTS_LIVE_FOCUS", True))

    def _get_favorites(self):
        """Set of (league, key) the person follows.

        SPORTS_MY_TEAMS holds league-qualified tokens ("nba:WSH,nfl:WSH").
        A numeric key is an ESPN team id ("college-football:120") and is kept
        as "#120"; college teams are saved that way.
        When it is empty, the legacy SPORTS_FAVORITE_TEAMS list of bare
        abbreviations applies to the primary league, through the alias map.
        """
        favorites = set()
        raw = str(getattr(config, "SPORTS_MY_TEAMS", "") or "")
        for token in raw.split(","):
            token = token.strip()
            if ":" not in token:
                continue
            league, abbr = token.split(":", 1)
            league = league.strip().lower()
            abbr = abbr.strip().upper()
            if league not in self.LEAGUES or not abbr:
                continue
            if abbr.isdigit():
                favorites.add((league, f"#{abbr}"))
            else:
                favorites.add((league, self.LEGACY_ABBR_ALIASES.get(league, {}).get(abbr, abbr)))
        if favorites:
            return favorites

        primary = self._get_league_key()
        aliases = self.LEGACY_ABBR_ALIASES.get(primary, {})
        legacy = str(getattr(config, "SPORTS_FAVORITE_TEAMS", "") or "")
        for token in legacy.split(","):
            abbr = token.strip().upper()
            if abbr:
                favorites.add((primary, aliases.get(abbr, abbr)))
        return favorites

    # ================================================================== update

    def update(self):
        """Lightweight: no HTTP here. The worker owns fetching."""
        now = time.time()
        config_manager.reload_config()

        signature = (tuple(self._get_league_keys()), self._get_test_date() or self._today_key(),
                     self._get_view_mode(), tuple(sorted(self._get_favorites())))
        if signature != self._fetch_signature:
            if self._fetch_signature is not None and signature[:2] != self._fetch_signature[:2]:
                self.current_game_index = 0
                self.placeholder_reason = "loading"
            self._fetch_signature = signature
            self._fetch_wake.set()

        self._apply_view_filter()
        self._note_score_changes(now)

        if len(self.games) > 1 and now - self.last_rotate >= self._hold_seconds(self.games[self.current_game_index]):
            self.current_game_index = (self.current_game_index + 1) % len(self.games)
            self.last_rotate = now

    def _apply_view_filter(self):
        previous_id = self.games[self.current_game_index].get("id") if self.games else None
        leagues = self._get_league_keys()
        all_games = [g for g in self.all_games if g.get("league") in leagues]
        if self._get_view_mode() == "favorites":
            favorites = self._get_favorites()
            base = [
                g for g in all_games
                if not self.LEAGUES[g["league"]].get("favorites", True) or self._is_favorite_game(g, favorites)
            ]
            if base:
                self.placeholder_reason = None
            elif not favorites and any(self.LEAGUES[k].get("favorites", True) for k in leagues):
                self.placeholder_reason = "pick a team"
            else:
                # Nothing today: rotate the upcoming games instead.
                base = self._upcoming_favorite_games(favorites)
                self.placeholder_reason = None if base else "no games today"
        else:
            base = all_games
            self.placeholder_reason = None if base else "no games today"

        if not self.all_games and self._fetch_signature is not None and not self._league_games:
            self.placeholder_reason = "offline" if self._fetch_failed else "loading"

        if self._get_live_focus():
            live = [g for g in base if g.get("state") == "in"]
            self.games = live if live else base
        else:
            self.games = base

        if previous_id:
            for idx, game in enumerate(self.games):
                if game.get("id") == previous_id:
                    self.current_game_index = idx
                    return
        self.current_game_index = 0

    def _hold_seconds(self, game):
        """How long a game stays up: long enough to show its leader frames."""
        if game.get("sport") == "basketball" and (game.get("state") == "post" or self._is_halftime(game)):
            leaders = sum(1 for side in ("away", "home") if game[side].get("leaders"))
            if leaders:
                return max(self.rotate_interval, self.STATUS_HOLD_SECONDS + self.LEADER_HOLD_SECONDS * leaders)
        return self.rotate_interval

    def _is_favorite_game(self, game, favorites):
        league = game.get("league")
        return any(key in favorites for key in self._team_keys(game, league))

    @staticmethod
    def _team_keys(game, league):
        for side in (game["away"], game["home"]):
            yield (league, side["abbr"])
            if side.get("id"):
                yield (league, f"#{side['id']}")

    def _note_score_changes(self, now):
        """Flash a score that just changed; jump to it in low-scoring sports.

        Basketball scores every half-minute, so there it only flashes if the
        game is already on screen.
        """
        if self._seen_generation == self._slate_generation:
            return
        self._seen_generation = self._slate_generation
        first_look = not self._score_memory

        for idx, game in enumerate(self.games):
            gid = game.get("id")
            scores = (game["away"]["score"], game["home"]["score"])
            before = self._score_memory.get(gid)
            self._score_memory[gid] = scores
            if first_look or before is None or game.get("state") != "in":
                continue
            for side, old, new in (("away", before[0], scores[0]), ("home", before[1], scores[1])):
                if new > old:
                    self._flash[gid] = (side, now + self.SCORE_FLASH_SECONDS)
                    if game.get("sport") != "basketball":
                        self.current_game_index = idx
                        self.last_rotate = now

        live_ids = {g.get("id") for g in self.all_games}
        for gid in [k for k in self._score_memory if k not in live_ids]:
            self._score_memory.pop(gid, None)
            self._flash.pop(gid, None)

    # =================================================================== fetch

    def _fetch_worker(self):
        """Daemon loop: fetch each selected league on its own cadence."""
        while True:
            now = time.time()
            try:
                self._run_due_fetches(now)
            except Exception as exc:
                print(f"Sports worker error: {exc}", flush=True)

            leagues = self._get_league_keys()
            due = [self._next_fetch_at.get(k, 0) for k in leagues]
            wait_seconds = max(1.0, min(due) - time.time()) if due else 5.0
            self._fetch_wake.wait(timeout=min(wait_seconds, self.POLL_IDLE))
            if self._fetch_wake.is_set():
                self._fetch_wake.clear()
                # A settings change: refetch everything now.
                self._next_fetch_at = {}

    def _run_due_fetches(self, now):
        leagues = self._get_league_keys()
        date_key = self._get_test_date() or self._today_key()
        changed = False

        for league in leagues:
            if now < self._next_fetch_at.get(league, 0):
                continue
            games = self._fetch_league(league, date_key)
            if games is None:
                self._fetch_failed.add(league)
                delay = self._failure_delay.get(league, 15)
                self._failure_delay[league] = min(300, delay * 2)
                self._next_fetch_at[league] = now + delay
                continue
            self._failure_delay[league] = 15
            self._fetch_failed.discard(league)
            self._league_games[league] = (date_key, games)
            self._next_fetch_at[league] = now + self._poll_interval(league, games, now)
            changed = True

        # Drop leagues that were deselected or belong to another day.
        for league in list(self._league_games):
            if league not in leagues or self._league_games[league][0] != date_key:
                self._league_games.pop(league, None)
                changed = True

        if changed:
            merged = [g for _, games in self._league_games.values() for g in games]
            merged.sort(key=self._sort_key)
            self.all_games = merged
            self._slate_generation += 1

        if self._get_view_mode() == "favorites":
            self._refresh_favorite_schedules(now)

    def _poll_interval(self, league, games, now):
        shown = {g.get("id") for g in self.games}
        # Before anything is on screen (first fetch), assume live is shown.
        if any(g.get("state") == "in" and (not shown or g.get("id") in shown) for g in games):
            return self.POLL_LIVE_SHOWN
        if any(g.get("state") == "in" for g in games):
            return self.POLL_LIVE_OTHER
        if any(g.get("state") == "pre" and 0 <= g.get("date_ts", 0) - now < 15 * 60 for g in games):
            return self.POLL_STARTING_SOON
        return self.POLL_IDLE

    def _get_json(self, url):
        try:
            response = self._session.get(url, timeout=8)
            if response.status_code != 200:
                return None
            return response.json()
        except Exception as exc:
            print(f"Sports API error: {exc}", flush=True)
            return None

    def _fetch_league(self, league, date_key):
        if self.LEAGUES[league].get("per_team") and self._get_view_mode() == "favorites":
            return self._fetch_followed_teams(league, time.time())
        path = self.LEAGUES[league]["path"]
        payload = self._get_json(f"{ESPN_SITE}/{path}/scoreboard?dates={date_key}")
        if payload is None:
            return None
        games = []
        for event in payload.get("events", []):
            try:
                game = self._parse_event(event, league)
            except Exception as exc:
                print(f"Sports: skipping unreadable event: {exc}", flush=True)
                game = None
            if game:
                games.append(game)
        return games

    def _fetch_followed_teams(self, league, now):
        """Today's game for each followed school, from the team endpoint.

        /teams/{id} is ~18 KB and its nextEvent carries the live score and
        status, and stays on a finished game until the next one is due.
        A game that is not today becomes that team's "next game".
        """
        path = self.LEAGUES[league]["path"]
        ids = sorted(key[1:] for lg, key in self._get_favorites() if lg == league and key.startswith("#"))
        games = {}
        reached = False
        for team_id in ids:
            payload = self._get_json(f"{ESPN_SITE}/{path}/teams/{team_id}")
            if payload is None:
                continue
            reached = True
            team = payload.get("team") or {}
            self._remember_color(league, team)
            upcoming = []
            for event in team.get("nextEvent") or []:
                game = self._parse_event(event, league)
                if not game:
                    continue
                if self._is_today(game, now):
                    games[game["id"]] = game
                elif game["state"] == "pre" and game["date_ts"] > now:
                    upcoming.append(dict(game, upcoming=True))
            self._schedule_cache[(league, f"#{team_id}")] = (now, self._pick_upcoming(upcoming, now))
        if ids and not reached:
            return None
        cached = [g for (lg, _), (_, games_) in self._schedule_cache.items() if lg == league for g in games_]
        for game in list(games.values()) + cached:
            self._fill_colors(league, game)
        return list(games.values())

    def _is_today(self, game, now):
        if game["state"] == "in":
            return True
        start = game.get("date_ts", 0)
        if game["state"] == "post":
            return 0 <= now - start < 16 * 3600
        try:
            return datetime.fromtimestamp(start).date() == datetime.fromtimestamp(now).date()
        except Exception:
            return False

    def _remember_color(self, league, team):
        team_id = str(team.get("id") or "")
        if team_id:
            self._color_cache[(league, team_id)] = (team.get("color"), team.get("alternateColor"))

    def _fill_colors(self, league, game):
        """Team endpoints don't colour the opponent; look each school up once."""
        path = self.LEAGUES[league]["path"]
        for side in (game["away"], game["home"]):
            team_id = side.get("id")
            if not team_id or side.get("colored"):
                continue
            if (league, team_id) not in self._color_cache:
                payload = self._get_json(f"{ESPN_SITE}/{path}/teams/{team_id}") or {}
                self._color_cache[(league, team_id)] = (
                    (payload.get("team") or {}).get("color"),
                    (payload.get("team") or {}).get("alternateColor"),
                )
            color, alt = self._color_cache[(league, team_id)]
            side["color"] = self._team_color(color, alt)
            side["colored"] = True

    def _refresh_favorite_schedules(self, now):
        """Keep each followed team's next game, for days they do not play.

        Scoreboards only cover one day, so without this the panel would say
        "no games" all week between NFL Sundays.
        """
        favorites = self._get_favorites()
        leagues = set(self._get_league_keys())
        playing_today = {key for g in self.all_games for key in self._team_keys(g, g["league"])}
        for league, abbr in favorites:
            if league not in leagues or (league, abbr) in playing_today:
                continue
            if self.LEAGUES[league].get("per_team") or abbr.startswith("#"):
                continue  # the per-team fetch keeps these
            cached = self._schedule_cache.get((league, abbr))
            if cached and now - cached[0] < self.SCHEDULE_TTL:
                continue
            team = self._team_info(league, abbr, now)
            if not team:
                continue
            path = self.LEAGUES[league]["path"]
            payload = self._get_json(f"{ESPN_SITE}/{path}/teams/{team['id']}/schedule")
            upcoming = []
            if payload:
                for event in payload.get("events", []):
                    game = self._parse_event(event, league)
                    if game and game["state"] == "pre" and game.get("date_ts", 0) > now:
                        upcoming.append(dict(game, upcoming=True))
            self._schedule_cache[(league, abbr)] = (now, self._pick_upcoming(upcoming, now))

    def _pick_upcoming(self, games, now):
        """A team's games in the next week, or at least its next one."""
        games = sorted(games, key=lambda g: g["date_ts"])
        soon = [g for g in games if g["date_ts"] - now <= self.UPCOMING_WINDOW]
        return (soon or games[:1])[: self.UPCOMING_PER_TEAM]

    def _team_info(self, league, abbr, now):
        if now - self._team_index_at.get(league, 0) > self.TEAM_INDEX_TTL:
            path = self.LEAGUES[league]["path"]
            payload = self._get_json(f"{ESPN_SITE}/{path}/teams")
            index = {}
            try:
                for entry in payload["sports"][0]["leagues"][0]["teams"]:
                    team = entry.get("team") or {}
                    key = str(team.get("abbreviation") or "").upper()
                    if key:
                        index[key] = {
                            "id": str(team.get("id") or ""),
                            "color": team.get("color"),
                            "alternateColor": team.get("alternateColor"),
                        }
            except Exception:
                index = {}
            if index:
                self._team_index[league] = index
                self._team_index_at[league] = now
            else:
                self._team_index_at[league] = now - self.TEAM_INDEX_TTL + 600
        return (self._team_index.get(league) or {}).get(abbr)

    def _upcoming_favorite_games(self, favorites):
        """Every followed team's upcoming games, soonest first.

        A game between two followed teams appears once.
        """
        now = time.time()
        leagues = set(self._get_league_keys())
        found = {}
        for (league, key), (_, games) in list(self._schedule_cache.items()):
            if league not in leagues or (league, key) not in favorites:
                continue
            for game in games:
                if game["date_ts"] > now:
                    found.setdefault(game["id"], game)
        return sorted(found.values(), key=lambda g: g["date_ts"])[: self.UPCOMING_MAX]

    # ================================================================= parsing

    def _parse_event(self, event, league=None):
        league = league or self._get_league_key()
        sport = self.LEAGUES[league]["sport"]
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

        game = {
            "id": str(event.get("id", "")),
            "league": league,
            "sport": sport,
            "state": state,
            "status_name": str(status_type.get("name") or "").upper(),
            "period": self._as_int(status.get("period"), 0),
            "clock": status.get("displayClock") or "",
            "detail": status_type.get("shortDetail") or status_type.get("detail") or status_type.get("description") or "",
            "date_ts": self._parse_timestamp(event.get("date") or competition.get("date")),
            "time_valid": event.get("timeValid", competition.get("timeValid", True)) is not False,
            "away": self._parse_team(away, league),
            "home": self._parse_team(home, league),
            "situation": {},
        }

        situation = competition.get("situation") or {}
        # No possession or down & distance: the free ESPN feed runs behind
        # the broadcast, and per-play detail is where that lag shows most.
        if sport == "baseball":
            game["situation"] = {
                "outs": self._as_int(situation.get("outs"), 0),
                "bases": (bool(situation.get("onFirst")), bool(situation.get("onSecond")), bool(situation.get("onThird"))),
            }
        return game

    def _parse_team(self, competitor, league):
        team = competitor.get("team") or {}
        abbr = str(team.get("abbreviation") or team.get("shortDisplayName") or "---").upper()
        # Full abbreviation: favourites match on it. Drawing fits it later.
        abbr = "".join(ch for ch in abbr if ch.isalnum()) or "---"
        records = competitor.get("records") or competitor.get("record") or []
        record = ""
        if isinstance(records, list) and records:
            record = str(records[0].get("summary") or records[0].get("displayValue") or "")
        color_hex = team.get("color")
        alt_hex = team.get("alternateColor")
        team_id = str(competitor.get("id") or team.get("id") or "")
        if not color_hex:
            known = (self._team_index.get(league) or {}).get(abbr) or {}
            color_hex, alt_hex = known.get("color"), known.get("alternateColor")
        if not color_hex and (league, team_id) in self._color_cache:
            color_hex, alt_hex = self._color_cache[(league, team_id)]
        rank = (competitor.get("curatedRank") or {}).get("current")
        rank = self._as_int(rank, 0)
        score = competitor.get("score")
        if isinstance(score, dict):
            score = score.get("displayValue") or score.get("value")
        return {
            "abbr": abbr,
            "score": self._as_int(score, 0),
            "record": record,
            "leaders": self._extract_leaders(competitor),
            "color": self._team_color(color_hex, alt_hex),
            "colored": bool(color_hex),
            "rank": rank if 1 <= rank <= 25 else 0,
            "id": team_id,
        }

    def _extract_leaders(self, competitor):
        """Top points scorer only: that is all the panel has room for."""
        for group in competitor.get("leaders") or []:
            name = str(group.get("name") or group.get("abbreviation") or "").lower()
            if name not in {"points", "pts"}:
                continue
            for item in (group.get("leaders") or [])[:1]:
                athlete = item.get("athlete") or {}
                player = self._display_player_name(
                    athlete.get("shortName") or athlete.get("displayName") or athlete.get("fullName") or ""
                )
                value = self._short_leader_value(item.get("displayValue") or item.get("value"))
                if player and value:
                    return {"name": player, "val": value}
        return None

    # ==================================================================== draw

    def draw(self):
        self.canvas = Image.new("RGB", (self.width, self.height), (0, 0, 0))
        draw = ImageDraw.Draw(self.canvas)

        if not self.games:
            self._draw_placeholder(draw)
            return self.canvas

        self._draw_game(draw, self.games[self.current_game_index % len(self.games)])
        return self.canvas

    def _draw_game(self, draw, game):
        self._draw_status_row(draw, game)
        self._draw_team_row(draw, game, "away", self.AWAY_Y)
        self._draw_team_row(draw, game, "home", self.HOME_Y)

    def _draw_placeholder(self, draw):
        reason = (self.placeholder_reason or "no games today").upper()
        if reason == "LOADING":
            head, sub = "LOADING", ""
        elif reason == "OFFLINE":
            head, sub = "NO SCORES", "RETRYING"
        elif reason == "PICK A TEAM":
            head, sub = "MY TEAMS", "PICK A TEAM"
        else:
            head, sub = "NO GAMES", "TODAY"

        leagues = " ".join(self.LEAGUES[k]["short"] for k in self._get_league_keys())
        leagues = self._fit_text(leagues, self.width - 4, self.font_small)
        self._center_text(draw, leagues, 2, self.font_small, self.color_dim)
        self._center_text(draw, head, 12, self.font_tall, self.color_text)
        if sub:
            self._center_text(draw, self._fit_text(sub, self.width - 2, self.font_small), 23, self.font_small, self.color_dim)

    # ------------------------------------------------------------- status row

    def _draw_status_row(self, draw, game):
        state = game.get("state")
        sport = game.get("sport")

        if state == "in" and sport == "baseball" and self._draw_baseball_status(draw, game):
            return

        if sport == "basketball" and (state == "post" or self._is_halftime(game)):
            frame = self._leader_frame(game)
            if frame is not None:
                team, leader = frame
                self._draw_leader_status(draw, team, leader)
                return

        if state == "in" and self._draw_clock_status(draw, game):
            return

        text = self._fit_text(self._status_text(game), self.width - 2, self.font_tall)
        color = self.color_dim if state == "post" else self.color_text
        self._center_text(draw, text, 0, self.font_tall, color)

    def _leader_frame(self, game):
        """Which frame of the halftime/final cycle is showing.

        STATUS_HOLD shows HALFTIME / FINAL, then each side's top scorer for
        LEADER_HOLD. Returns None for the status frame.
        """
        frames = [None]
        for side in ("away", "home"):
            leader = game[side].get("leaders")
            if leader:
                frames.append((game[side], leader))
        if len(frames) == 1:
            return None
        cycle = self.STATUS_HOLD_SECONDS + self.LEADER_HOLD_SECONDS * (len(frames) - 1)
        t = (time.time() - self.last_rotate) % cycle
        if t < self.STATUS_HOLD_SECONDS:
            return None
        return frames[1 + int((t - self.STATUS_HOLD_SECONDS) // self.LEADER_HOLD_SECONDS)]

    def _draw_leader_status(self, draw, team, leader):
        value = leader["val"]
        value_w = int(self.font_tall.getlength(value))
        name_max = self.width - (self.BAR_WIDTH + 2) - value_w - 5 - 1
        name = self._fit_text(leader["name"], name_max, self.font_tall, ellipsis="")
        name_w = int(self.font_tall.getlength(name))
        total = self.BAR_WIDTH + 2 + name_w + 5 + value_w
        x = max(0, (self.width - total) // 2)
        draw.rectangle((x, 1, x + self.BAR_WIDTH - 1, 7), fill=team["color"])
        x += self.BAR_WIDTH + 2
        draw.text((x, 0), name, font=self.font_tall, fill=self.color_dim)
        draw.text((x + name_w + 5, 0), value, font=self.font_tall, fill=self.color_text)

    def _draw_clock_status(self, draw, game):
        """Period + game clock, with a 1px-dot colon instead of the font's."""
        detail = str(game.get("detail", "")).upper()
        if game.get("sport") == "soccer" or self._is_halftime(game) or "END" in detail:
            return False
        clock = str(game.get("clock") or "")
        if ":" not in clock:
            return False
        mins, secs = clock.split(":", 1)
        if not mins or not secs:
            return False

        period_text = f"{self._period_label(game)} "
        period_w = int(self.font_tall.getlength(period_text))
        mins_w = int(self.font_tall.getlength(mins))
        secs_w = int(self.font_tall.getlength(secs))
        total_w = period_w + mins_w + 2 + secs_w
        x = max(0, (self.width - total_w) // 2)

        draw.text((x, 0), period_text, font=self.font_tall, fill=self.color_dim)
        x += period_w
        draw.text((x, 0), mins, font=self.font_tall, fill=self.color_text)
        x += mins_w
        draw.point((x, 3), fill=self.color_text)
        draw.point((x, 6), fill=self.color_text)
        x += 2
        draw.text((x, 0), secs, font=self.font_tall, fill=self.color_text)
        return True

    def _draw_baseball_status(self, draw, game):
        half, inning = self._baseball_half(game)
        if half in {"MID", "END"} or not half:
            return False

        # Half-inning arrow and number, left.
        if half == "TOP":
            draw.polygon([(3, 2), (0, 5), (6, 5)], fill=self.color_accent)
        else:
            draw.polygon([(0, 2), (6, 2), (3, 5)], fill=self.color_accent)
        draw.text((8, 0), str(inning), font=self.font_tall, fill=self.color_text)

        # Bases, centre: second on top, third left, first right.
        first, second, third = game["situation"].get("bases", (False, False, False))
        for (cx, cy), on in (((32, 2), second), ((28, 6), third), ((36, 6), first)):
            self._draw_base(draw, cx, cy, on)

        # Outs, right: three dots.
        outs = min(3, game["situation"].get("outs", 0))
        for i in range(3):
            x = 51 + i * 4
            draw.rectangle((x, 3, x + 2, 5), fill=self.color_accent if i < outs else self.color_faint)
        return True

    def _draw_base(self, draw, cx, cy, on):
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                d = abs(dx) + abs(dy)
                if d > 2:
                    continue
                if on:
                    draw.point((cx + dx, cy + dy), fill=self.color_accent)
                elif d == 2:
                    draw.point((cx + dx, cy + dy), fill=self.color_dim)

    # --------------------------------------------------------------- team row

    def _draw_team_row(self, draw, game, side, y):
        team = game[side]
        other = game["home"] if side == "away" else game["away"]
        state = game.get("state")

        text_color = self.color_text
        if state == "post" and team["score"] < other["score"]:
            text_color = self.color_loser

        flash = self._flash.get(game.get("id"))
        flashing = bool(flash and flash[0] == side and time.time() < flash[1])
        if flashing and int(time.time() * 4) % 2 == 0:
            text_color = self.color_accent

        draw.rectangle((0, y + 1, self.BAR_WIDTH - 1, y + 8), fill=team["color"])

        team_x = self.BAR_WIDTH + 2
        abbr = self._fit_text(team["abbr"], 25, self.font_tall, ellipsis="")
        draw.text((team_x, y), abbr, font=self.font_tall, fill=text_color)
        cursor = team_x + int(self.font_tall.getlength(abbr)) + 2

        # AP rank for college teams, small and dim, right after the name.
        if team.get("rank"):
            rank = str(team["rank"])
            draw.text((cursor, y + 2), rank, font=self.font_small, fill=self.color_dim)
            cursor += int(self.font_small.getlength(rank)) + 2

        # Right side: the score, or the record before the game.
        if state == "pre":
            right = team.get("record") or ""
            if re.fullmatch(r"[0\-]+", right):
                right = ""  # 0-0 before a season starts says nothing
            right_w = int(self.font_small.getlength(right))
            right_x = self.width - right_w - 1
            if right and right_x > cursor + 2:
                draw.text((right_x, y + 2), right, font=self.font_small, fill=self.color_dim)
            return

        score = str(team["score"])
        score_w = int(self.font_tall.getlength(score))
        score_x = self.width - score_w - 1
        draw.text((score_x, y), score, font=self.font_tall, fill=text_color)

    # ================================================================= helpers

    def _status_text(self, game):
        """Short status string; also used by the Custom Widget's sports slot."""
        state = game.get("state")
        detail = str(game.get("detail", "")).upper()
        sport = game.get("sport") or "basketball"
        status_name = game.get("status_name") or ""

        if "POSTPONED" in status_name or "POSTPONED" in detail:
            return "POSTPONED"
        if "CANCEL" in status_name or "CANCEL" in detail:
            return "CANCELED"
        if "DELAY" in status_name or "DELAY" in detail:
            return "DELAYED"

        if state == "pre":
            return self._start_text(game)

        if state == "post":
            if sport == "soccer":
                if "PEN" in detail:
                    return "FT PENS"
                if "AET" in detail or "EXTRA" in detail:
                    return "AET"
                return "FT"
            if sport == "baseball":
                inning = self._as_int(game.get("period"), 9)
                return f"FINAL/{inning}" if inning > 9 else "FINAL"
            if "OT" in detail or "SO" in detail:
                label = detail.split("/", 1)[-1].strip() if "/" in detail else "OT"
                return f"FINAL/{label}"
            return "FINAL"

        if sport == "soccer":
            return self._soccer_live_status(game, detail)
        if sport == "baseball":
            half, inning = self._baseball_half(game)
            return f"{half} {inning}" if half else "LIVE"
        if self._is_halftime(game):
            return "HALFTIME"
        if "END" in detail:
            return f"END {self._period_label(game, game.get('period'))}"
        clock = game.get("clock") or ""
        return f"{self._period_label(game)} {clock}".strip()

    def _start_text(self, game):
        ts = game.get("date_ts", 0.0)
        if not ts:
            return "SCHEDULED"
        try:
            start = datetime.fromtimestamp(ts)
        except Exception:
            return "SCHEDULED"
        clock = start.strftime("%I:%M%p").lstrip("0").replace("AM", "A").replace("PM", "P")
        today = datetime.now().date()
        if not game.get("time_valid", True):
            clock = "TBD"
        if start.date() == today:
            return clock
        if start.date() - today < timedelta(days=7):
            return f"{start.strftime('%a').upper()} {clock}"
        return f"{start.month}/{start.day} {clock}"

    def _is_halftime(self, game):
        detail = str(game.get("detail", "")).upper()
        return "HALFTIME" in detail or detail in {"HT", "HALF"} or "HALFTIME" in (game.get("status_name") or "")

    def _baseball_half(self, game):
        detail = str(game.get("detail", "")).upper()
        inning = self._as_int(game.get("period"), 0) or 1
        for key, label in (("TOP", "TOP"), ("BOT", "BOT"), ("MID", "MID"), ("END", "END")):
            if detail.startswith(key):
                return label, inning
        return "", inning

    def _soccer_live_status(self, game, detail):
        if self._is_halftime(game):
            return "HT"
        if "PEN" in detail or "SHOOTOUT" in detail:
            return "PENS"
        clock = str(game.get("clock") or "").strip()
        if clock:
            return clock
        match = re.search(r"(\d{1,3})(?:\s*\+\s*(\d{1,2}))?", detail)
        if match:
            minute, stoppage = match.group(1), match.group(2)
            return f"{minute}+{stoppage}'" if stoppage else f"{minute}'"
        return "LIVE"

    def _period_label(self, game, period=None):
        sport = game.get("sport") if isinstance(game, dict) else self._get_league()["sport"]
        if period is None:
            period = game.get("period", 0) if isinstance(game, dict) else game
        p = self._as_int(period, 0)
        detail = str(game.get("detail", "")).upper() if isinstance(game, dict) else ""

        if sport == "soccer":
            return "1H" if p <= 1 else "2H" if p == 2 else "ET"
        if sport == "hockey":
            if "SO" in detail.split():
                return "SO"
            if p <= 3:
                return f"P{max(1, p)}"
            return "OT" if p == 4 else f"{p - 3}OT"
        league = self.LEAGUES.get(game.get("league") if isinstance(game, dict) else "", {})
        if league.get("halves"):
            if p <= 2:
                return f"{max(1, p)}H"
            return "OT" if p == 3 else f"{p - 2}OT"
        if p <= 4:
            return f"Q{max(1, p)}"
        return "OT" if p == 5 else f"{p - 4}OT"

    def _sort_key(self, game):
        state_order = {"in": 0, "pre": 1, "post": 2}.get(game.get("state"), 3)
        ts = game.get("date_ts", 0.0)
        return (state_order, -ts if state_order == 2 else ts)

    def _center_text(self, draw, text, y, font, color):
        w = int(font.getlength(text))
        draw.text(((self.width - w) // 2, y), text, font=font, fill=color)

    def _fit_text(self, text, max_width, font, ellipsis="..."):
        if not text:
            return ""
        text = str(text)
        if int(font.getlength(text)) <= max_width:
            return text
        while text and int(font.getlength(text + ellipsis)) > max_width:
            text = text[:-1]
        return (text + ellipsis) if text else ""

    def _display_player_name(self, name):
        cleaned = re.sub(r"[^A-Za-z\-' ]", " ", str(name or ""))
        parts = [p for p in cleaned.split() if p]
        if not parts:
            return ""
        return (parts[-1] if len(parts) > 1 else parts[0]).upper()

    def _short_leader_value(self, value):
        match = re.search(r"\d+", str(value or ""))
        return match.group(0)[:3] if match else ""

    def _team_color(self, color_hex, alt_hex):
        """A team colour that reads on black.

        Many primaries are near-black (Penguins, Spurs, LAFC). Try the
        alternate colour first, then lift the primary's brightness while
        keeping its hue, rather than washing it to grey.
        """
        for candidate in (color_hex, alt_hex):
            rgb = self._hex_rgb(candidate)
            if rgb and max(rgb) >= 100 and self._luma(rgb) >= 28:
                return rgb
        rgb = self._hex_rgb(color_hex) or self._hex_rgb(alt_hex)
        if not rgb:
            return self.color_neutral_team
        peak = max(rgb)
        if peak < 24:
            return self.color_neutral_team
        scale = max(1.0, 160.0 / peak)
        return tuple(min(255, int(c * scale)) for c in rgb)

    @staticmethod
    def _hex_rgb(value):
        raw = str(value or "").strip().lstrip("#")
        if len(raw) != 6:
            return None
        try:
            return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))
        except ValueError:
            return None

    @staticmethod
    def _luma(rgb):
        r, g, b = rgb
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def _parse_timestamp(self, iso_time):
        if not iso_time:
            return 0.0
        try:
            return datetime.fromisoformat(str(iso_time).replace("Z", "+00:00")).timestamp()
        except Exception:
            return 0.0

    def _as_int(self, value, default):
        try:
            return int(float(value))
        except Exception:
            return default
