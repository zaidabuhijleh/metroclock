import importlib
import time

import requests
from PIL import Image, ImageDraw, ImageFont

import config
from core.widget import Widget


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# (range, interval) pairs for Yahoo's chart endpoint.
TIMEFRAMES = {
    "1D":  {"range": "1d",  "interval": "5m"},
    "1W":  {"range": "5d",  "interval": "30m"},
    "1M":  {"range": "1mo", "interval": "1d"},
}
TIMEFRAME_ORDER = ["1D", "1W", "1M"]


class StocksWidget(Widget):
    """Stock ticker with two views.

    "ticker": single horizontally-scrolling row of SYM PRICE +/-%.
    "focus":  one stock at a time with a sparkline anchored to previous close.
    """

    COLOR_TEXT = (236, 240, 252)
    COLOR_DIM = (140, 156, 192)
    COLOR_FAINT = (70, 86, 110)
    COLOR_UP = (88, 220, 128)
    COLOR_DOWN = (240, 92, 92)
    COLOR_FLAT = (200, 200, 200)
    COLOR_BASELINE = (60, 70, 92)
    COLOR_AFTER_HOURS = (255, 196, 72)
    COLOR_BG = (0, 0, 0)

    DEFAULT_SYMBOLS = ["AAPL", "TSLA", "NVDA", "SPY"]

    def __init__(self, width, height):
        super().__init__(width, height)

        self.cache = {}              # (symbol, timeframe) -> parsed dict
        self.last_fetch = {}         # (symbol, timeframe) -> ts
        self.user_agent = "Mozilla/5.0 (compatible; metroclock-stocks/1.0)"

        self.focus_index = 0
        self.last_focus_rotate = time.time()
        self.cycle_tf_index = 0

        self.ticker_offset = 0.0
        self.last_ticker_step = time.time()
        self._strip_sig = None
        self._strip_img = None

        self.placeholder = None

        try:
            self.font_tall = ImageFont.truetype(config.FONT_PATH_TALL, 10)
        except Exception:
            self.font_tall = ImageFont.load_default()
        try:
            self.font_small = ImageFont.truetype(config.FONT_PATH_SMALL, 6)
        except Exception:
            self.font_small = ImageFont.load_default()

    # ------------------------------------------------------------- config

    def _symbols(self):
        raw = str(getattr(config, "STOCKS_SYMBOLS", "") or "")
        seen, ordered = set(), []
        for s in (s.strip().upper() for s in raw.split(",")):
            if s and s not in seen:
                seen.add(s)
                ordered.append(s)
        return ordered or list(self.DEFAULT_SYMBOLS)

    def _view_mode(self):
        v = str(getattr(config, "STOCKS_VIEW_MODE", "ticker") or "ticker").lower()
        return v if v in {"ticker", "focus"} else "ticker"

    def _timeframe_setting(self):
        tf = str(getattr(config, "STOCKS_FOCUS_TIMEFRAME", "1D") or "1D").upper()
        if tf == "CYCLE":
            return "cycle"
        return tf if tf in TIMEFRAMES else "1D"

    def _ticker_speed(self):
        try:
            return max(5.0, min(80.0, float(getattr(config, "STOCKS_TICKER_SPEED", 25))))
        except Exception:
            return 25.0

    def _focus_rotate_interval(self):
        try:
            return max(2.0, float(getattr(config, "STOCKS_FOCUS_ROTATE_SECONDS", 8)))
        except Exception:
            return 8.0

    def _current_timeframe(self):
        setting = self._timeframe_setting()
        if setting == "cycle":
            return TIMEFRAME_ORDER[self.cycle_tf_index % len(TIMEFRAME_ORDER)]
        return setting

    # ------------------------------------------------------------- update

    def update(self):
        importlib.reload(config)
        now = time.time()

        symbols = self._symbols()
        if not symbols:
            self.placeholder = "ADD STOCKS"
            return
        self.placeholder = None

        view_mode = self._view_mode()
        timeframe_setting = self._timeframe_setting()
        cycle_focus = timeframe_setting == "cycle" and view_mode == "focus"

        rotate_interval = self._focus_rotate_interval()
        if symbols and now - self.last_focus_rotate >= rotate_interval:
            if cycle_focus:
                # Cycle all timeframes for the current symbol before moving
                # on to the next symbol.
                self.cycle_tf_index = (self.cycle_tf_index + 1) % len(TIMEFRAME_ORDER)
                if self.cycle_tf_index == 0:
                    self.focus_index = (self.focus_index + 1) % len(symbols)
            else:
                self.focus_index = (self.focus_index + 1) % len(symbols)
                self.cycle_tf_index = 0
            self.last_focus_rotate = now
        elif not cycle_focus:
            self.cycle_tf_index = 0

        # Only fetch what's actually being shown.
        if view_mode == "ticker":
            needed = {"1D"}
        else:
            needed = {self._current_timeframe()}

        market_state = self._derive_market_state()
        fetch_interval = 30.0 if market_state == "REGULAR" else 600.0

        for sym in symbols:
            for tf in needed:
                key = (sym, tf)
                if key in self.cache and now - self.last_fetch.get(key, 0) < fetch_interval:
                    continue
                self._fetch_chart(sym, tf)
                self.last_fetch[key] = now

    def _derive_market_state(self):
        for data in self.cache.values():
            ms = data.get("market_state") or ""
            if ms:
                return ms
        return "REGULAR"

    def _fetch_chart(self, symbol, timeframe):
        cfg = TIMEFRAMES.get(timeframe) or TIMEFRAMES["1D"]
        url = YAHOO_CHART_URL.format(symbol=symbol)
        params = {
            "range": cfg["range"],
            "interval": cfg["interval"],
            "includePrePost": "true",
        }
        try:
            resp = requests.get(
                url,
                params=params,
                timeout=8,
                headers={"User-Agent": self.user_agent, "Accept": "application/json"},
            )
            if resp.status_code != 200:
                return
            payload = resp.json()
        except Exception as exc:
            print(f"Stocks API error ({symbol}/{timeframe}): {exc}")
            return

        parsed = self._parse_chart(payload)
        if parsed:
            self.cache[(symbol, timeframe)] = parsed

    def _parse_chart(self, payload):
        try:
            result = (payload.get("chart", {}).get("result") or [])[0]
        except (IndexError, AttributeError):
            return None
        if not result:
            return None

        meta = result.get("meta") or {}
        timestamps = result.get("timestamp") or []
        quote_list = (result.get("indicators", {}) or {}).get("quote") or [{}]
        closes = quote_list[0].get("close") or []

        series = [(ts, c) for ts, c in zip(timestamps, closes) if c is not None]

        last_price = meta.get("regularMarketPrice")
        if last_price is None and series:
            last_price = series[-1][1]

        prev_close = meta.get("chartPreviousClose")
        if prev_close is None:
            prev_close = meta.get("previousClose")

        return {
            "symbol": meta.get("symbol", ""),
            "currency": meta.get("currency", "USD"),
            "market_state": str(meta.get("marketState", "")).upper(),
            "last_price": last_price,
            "prev_close": prev_close,
            "series": series,
        }

    # ---------------------------------------------------------------- draw

    def draw(self):
        self.canvas = Image.new("RGB", (self.width, self.height), self.COLOR_BG)
        draw = ImageDraw.Draw(self.canvas)

        if self.placeholder:
            self._draw_placeholder(draw, self.placeholder)
            return self.canvas

        if self._view_mode() == "ticker":
            self._draw_ticker()
        else:
            self._draw_focus(draw)

        return self.canvas

    def _draw_placeholder(self, draw, msg):
        title = "STOCKS"
        tw = int(self.font_tall.getlength(title))
        draw.text(((self.width - tw) // 2, 5), title, font=self.font_tall, fill=self.COLOR_TEXT)
        sw = int(self.font_small.getlength(msg))
        draw.text(((self.width - sw) // 2, 19), msg, font=self.font_small, fill=self.COLOR_DIM)

    # ---- ticker -------------------------------------------------------

    def _draw_ticker(self):
        items = self._ticker_items()
        if not items:
            self._draw_placeholder(ImageDraw.Draw(self.canvas), "LOADING")
            return

        strip = self._build_ticker_strip(items)
        if strip is None or strip.width <= 0:
            self._draw_placeholder(ImageDraw.Draw(self.canvas), "LOADING")
            return

        now = time.time()
        dt = now - self.last_ticker_step
        self.last_ticker_step = now
        if dt < 0 or dt > 0.5:
            dt = 0.05
        self.ticker_offset = (self.ticker_offset + dt * self._ticker_speed()) % strip.width

        src_x = int(self.ticker_offset)
        first_w = min(self.width, strip.width - src_x)
        if first_w > 0:
            self.canvas.paste(
                strip.crop((src_x, 0, src_x + first_w, strip.height)),
                (0, 0),
            )
        if first_w < self.width:
            remaining = self.width - first_w
            self.canvas.paste(
                strip.crop((0, 0, remaining, strip.height)),
                (first_w, 0),
            )

    def _ticker_items(self):
        items = []
        for sym in self._symbols():
            data = self.cache.get((sym, "1D"))
            if not data or data.get("last_price") is None:
                continue
            items.append({
                "symbol": sym,
                "last_price": data["last_price"],
                "prev_close": data.get("prev_close"),
                "market_state": data.get("market_state", ""),
            })
        return items

    def _build_ticker_strip(self, items):
        sig = tuple(
            (it["symbol"], round(float(it["last_price"]), 4),
             round(float(it["prev_close"] or 0), 4), it["market_state"])
            for it in items
        )
        if sig == self._strip_sig and self._strip_img is not None:
            return self._strip_img

        gap = 10
        # Pre-compute widths using a temporary draw context.
        widths = []
        for it in items:
            sym_w = int(self.font_tall.getlength(it["symbol"]))
            price_w = self._measure_price_tall(self._fmt_price(it["last_price"]))
            pct_w = int(self.font_tall.getlength(self._fmt_pct(it["last_price"], it["prev_close"])))
            ah_w = 0
            if it["market_state"] in {"PRE", "POST"}:
                ah_w = int(self.font_small.getlength("AH")) + 2
            # SYM <space 3> price <space 3> arrow(3) <space 2> pct (+ optional AH tag)
            widths.append(sym_w + 3 + price_w + 3 + 3 + 2 + pct_w + ah_w)

        total_w = sum(widths) + gap * len(items)
        if total_w < self.width:
            total_w = self.width

        img = Image.new("RGB", (total_w, self.height), self.COLOR_BG)
        d = ImageDraw.Draw(img)

        y_text = (self.height - 10) // 2  # vertical center for 10px font

        x = 0
        for it, _w in zip(items, widths):
            change = self._change(it["last_price"], it["prev_close"])
            chg_color = self._change_color(change)

            d.text((x, y_text), it["symbol"], font=self.font_tall, fill=self.COLOR_TEXT)
            x += int(self.font_tall.getlength(it["symbol"])) + 3

            price_str = self._fmt_price(it["last_price"])
            self._draw_price_tall(d, x, y_text, price_str, self.COLOR_TEXT)
            x += self._measure_price_tall(price_str) + 3

            self._draw_arrow(d, x, y_text + 2, change >= 0, chg_color)
            x += 3 + 2

            pct_str = self._fmt_pct(it["last_price"], it["prev_close"])
            d.text((x, y_text), pct_str, font=self.font_tall, fill=chg_color)
            x += int(self.font_tall.getlength(pct_str))

            if it["market_state"] in {"PRE", "POST"}:
                x += 2
                d.text((x, y_text + 2), "AH", font=self.font_small, fill=self.COLOR_AFTER_HOURS)
                x += int(self.font_small.getlength("AH"))

            x += gap

        self._strip_sig = sig
        self._strip_img = img
        return img

    # ---- focus --------------------------------------------------------

    def _draw_focus(self, draw):
        symbols = self._symbols()
        if not symbols:
            self._draw_placeholder(draw, "ADD STOCKS")
            return

        sym = symbols[self.focus_index % len(symbols)]
        timeframe = self._current_timeframe()
        data = self.cache.get((sym, timeframe))

        # Header: symbol + price (or LOADING)
        draw.text((1, 0), sym, font=self.font_tall, fill=self.COLOR_TEXT)

        if not data or data.get("last_price") is None:
            loading = "..."
            lw = int(self.font_tall.getlength(loading))
            draw.text((self.width - lw - 1, 0), loading, font=self.font_tall, fill=self.COLOR_DIM)
            return

        last = data["last_price"]
        prev = data.get("prev_close")
        change = self._change(last, prev)
        chg_color = self._change_color(change)

        price_str = self._fmt_price(last)
        pw = self._measure_price_tall(price_str)
        self._draw_price_tall(draw, self.width - pw - 1, 0, price_str, self.COLOR_TEXT)

        # Sub row: change + timeframe label
        chg_str = self._fmt_change(last, prev, signed=False, with_dollar=True)
        pct_str = self._fmt_pct(last, prev, signed=False)
        # tag for after-hours/pre on top-left of sub-row
        ms = data.get("market_state", "")
        x_sub = 1
        if ms in {"PRE", "POST"}:
            tag = "PRE" if ms == "PRE" else "AH"
            tw = int(self.font_small.getlength(tag))
            draw.text((x_sub, 11), tag, font=self.font_small, fill=self.COLOR_AFTER_HOURS)
            x_sub += tw + 2
        elif ms == "CLOSED":
            tag = "CLD"
            tw = int(self.font_small.getlength(tag))
            draw.text((x_sub, 11), tag, font=self.font_small, fill=self.COLOR_DIM)
            x_sub += tw + 2

        tf_label = timeframe
        tw = int(self.font_small.getlength(tf_label))
        tf_x = self.width - tw - 1
        draw.text((tf_x, 11), tf_label, font=self.font_small, fill=self.COLOR_DIM)

        # Keep two-decimal percent visible; if space gets tight, trim change first.
        available = max(0, tf_x - x_sub - 1)
        sub = f"{chg_str} {pct_str}"
        sub_compact = f"{chg_str}{pct_str}"
        if int(self.font_small.getlength(sub)) <= available:
            sub_to_draw = sub
        elif int(self.font_small.getlength(sub_compact)) <= available:
            sub_to_draw = sub_compact
        else:
            pct_w = int(self.font_small.getlength(pct_str))
            if pct_w <= available:
                chg_max = max(0, available - pct_w - 1)
                chg_fit = self._fit_text(chg_str, chg_max, self.font_small, ellipsis="")
                sub_to_draw = f"{chg_fit} {pct_str}" if chg_fit else pct_str
            else:
                sub_to_draw = self._fit_text(pct_str, available, self.font_small, ellipsis="")

        self._draw_text_small_with_compact_plus(draw, x_sub, 11, sub_to_draw, chg_color)

        # Divider
        draw.line((0, 17, self.width - 1, 17), fill=self.COLOR_FAINT)

        # Sparkline area: y 18..31 (14 px tall)
        self._draw_sparkline(draw, data, prev, chg_color, y_top=18, y_bot=31)

    def _draw_sparkline(self, draw, data, prev_close, line_color, y_top, y_bot):
        series = data.get("series") or []
        if len(series) < 2:
            msg = "NO DATA"
            mw = int(self.font_small.getlength(msg))
            draw.text(((self.width - mw) // 2, y_top + 3), msg, font=self.font_small, fill=self.COLOR_DIM)
            return

        closes = [c for _, c in series]
        v_min = min(closes)
        v_max = max(closes)
        if prev_close is not None:
            v_min = min(v_min, prev_close)
            v_max = max(v_max, prev_close)
        v_range = (v_max - v_min) or max(abs(v_max) * 0.001, 0.01)
        height = y_bot - y_top

        def y_for(value):
            frac = (value - v_min) / v_range
            return y_bot - int(round(frac * height))

        # Baseline at previous close.
        if prev_close is not None:
            y_base = y_for(prev_close)
            for x in range(0, self.width, 2):  # dotted
                draw.point((x, y_base), fill=self.COLOR_BASELINE)

        # Polyline. Sample one close per x by mapping x linearly to series index.
        n = len(series)
        prev_y = y_for(closes[0])
        for x in range(1, self.width):
            idx = int(x * (n - 1) / (self.width - 1))
            yy = y_for(closes[idx])
            draw.line((x - 1, prev_y, x, yy), fill=line_color)
            prev_y = yy

    # ------------------------------------------------------------ helpers

    def _change(self, last, prev):
        try:
            if prev is None or prev == 0:
                return 0.0
            return float(last) - float(prev)
        except (TypeError, ValueError):
            return 0.0

    def _change_color(self, change):
        if change > 0:
            return self.COLOR_UP
        if change < 0:
            return self.COLOR_DOWN
        return self.COLOR_FLAT

    def _fmt_price(self, value):
        try:
            v = float(value)
        except (TypeError, ValueError):
            return "--"
        absv = abs(v)
        if absv >= 10000:
            return f"{v:.0f}"
        if absv >= 1000:
            return f"{v:.1f}"
        if absv >= 1:
            return f"{v:.2f}"
        return f"{v:.3f}"

    def _fmt_change(self, last, prev, signed=True, with_dollar=False):
        change = round(self._change(last, prev), 2)
        if change == -0.0:
            change = 0.0
        magnitude = f"{abs(change):.2f}"
        if with_dollar:
            magnitude = f"${magnitude}"
        if signed:
            sign = "+" if change >= 0 else "-"
            return f"{sign}{magnitude}"
        return magnitude

    def _fmt_pct(self, last, prev, signed=True):
        try:
            if prev is None or prev == 0:
                return "--%"
            pct = (float(last) - float(prev)) / float(prev) * 100.0
        except (TypeError, ValueError):
            return "--%"
        pct = round(pct, 2)
        if pct == -0.0:
            pct = 0.0
        magnitude = f"{abs(pct):.2f}%"
        if signed:
            sign = "+" if pct >= 0 else "-"
            return f"{sign}{magnitude}"
        return magnitude

    def _draw_arrow(self, draw, x, y, up, color):
        # 3x4 chunky triangle.
        if up:
            draw.point((x + 1, y), fill=color)
            draw.line((x, y + 1, x + 2, y + 1), fill=color)
            draw.line((x, y + 2, x + 2, y + 2), fill=color)
            draw.line((x, y + 3, x + 2, y + 3), fill=color)
        else:
            draw.line((x, y, x + 2, y), fill=color)
            draw.line((x, y + 1, x + 2, y + 1), fill=color)
            draw.line((x, y + 2, x + 2, y + 2), fill=color)
            draw.point((x + 1, y + 3), fill=color)

    def _fit_text(self, text, max_width, font, ellipsis="..."):
        if not text:
            return ""
        text = str(text)
        if int(font.getlength(text)) <= max_width:
            return text
        while text and int(font.getlength(text + ellipsis)) > max_width:
            text = text[:-1]
        return (text + ellipsis) if text else ""

    def _measure_price_tall(self, price_str):
        if "." not in price_str:
            return int(self.font_tall.getlength(price_str))
        whole, frac = price_str.split(".", 1)
        return int(self.font_tall.getlength(whole)) + 1 + int(self.font_tall.getlength(frac))

    def _draw_price_tall(self, draw, x, y, price_str, color):
        # Use a 1-pixel decimal dot for compact, cleaner price rendering.
        if "." not in price_str:
            draw.text((x, y), price_str, font=self.font_tall, fill=color)
            return
        whole, frac = price_str.split(".", 1)
        draw.text((x, y), whole, font=self.font_tall, fill=color)
        x_dot = x + int(self.font_tall.getlength(whole))
        y_dot = y + 8
        draw.point((x_dot, y_dot), fill=color)
        draw.text((x_dot + 1, y), frac, font=self.font_tall, fill=color)

    def _draw_text_small_with_compact_plus(self, draw, x, y, text, color):
        if not text:
            return
        cx = x
        plus_w = int(self.font_small.getlength("+"))
        for ch in text:
            if ch == "+":
                self._draw_compact_plus_small(draw, cx, y, color)
                cx += plus_w
            else:
                draw.text((cx, y), ch, font=self.font_small, fill=color)
                cx += int(self.font_small.getlength(ch))

    def _draw_compact_plus_small(self, draw, x, y, color):
        # Shorten vertical stroke by one pixel at top/bottom vs full-height plus.
        draw.line((x, y + 3, x + 3, y + 3), fill=color)
        draw.line((x + 1, y + 2, x + 1, y + 4), fill=color)
