# MetroClock — Claude Code Context

## What This Is
A Raspberry Pi Zero 2W powered 64x32 RGB LED matrix display that shows DC metro arrivals, weather, or flight tracking. Built to eventually sell on Etsy — needs to be easy for non-technical users to set up out of the box.

## Hardware
- **Pi Zero 2W**, user: `zaid`, hostname: `metroclock`, IP: `192.168.1.164`
- **64x32 RGB LED matrix** via Adafruit HAT
- GPIO config: `hardware_mapping='adafruit-hat'`, `pwm_bits=2`, `disable_hardware_pulsing=True`, `gpio_slowdown=4`
- Always run `main.py` with `sudo`
- `pip install` on Pi needs `--break-system-packages`; Flask must also be installed for root: `sudo pip3 install flask --break-system-packages`

## Repo Structure
```
main.py              # Entry point — starts web server thread, runs LED display loop
config.py            # All settings (API keys, hardware config, display mode)
config_manager.py    # Atomic read/write of config.py fields at runtime
web_server.py        # Flask API server (background thread, port 80)
web/index.html       # Settings webapp (single-page, served by Flask)
setup_hotspot.sh     # First-boot: broadcasts MetroClock-Setup WiFi hotspot
metroclock.service   # systemd unit for auto-start on boot
requirements.txt     # requests, Pillow, flask
core/
  display.py         # RGBMatrix wrapper — SetImage, clear (push is a no-op)
  widget.py          # Abstract base class for all widgets
widgets/
  metro.py           # WMATA DC metro arrivals
  weather.py         # OpenWeatherMap current conditions
  flight.py          # AviationStack flight tracker
  icons.py           # Pixel art weather icons (animated)
assets/fonts/        # BDF bitmap fonts: 6x10.bdf, 4x6.bdf
```

## How It Works
- `main.py` calls `web_server.start_server()` which launches Flask in a daemon thread, then runs the LED display loop
- Display mode (`metro`/`weather`/`flight`) is stored in a thread-safe `_display_mode` variable in `web_server.py` using `threading.Lock`
- `get_display_mode()` lazily initializes from `config.DISPLAY_MODE` on first call
- Web UI at `http://192.168.1.164` lets you switch modes live and save all settings
- Settings are written directly to `config.py` by `config_manager.py` using atomic writes (temp file + `os.replace`)
- After each write, `config` module is reloaded via `importlib.reload(config)`

## Web Server API
- `GET /api/status` — current mode, IP, hostname, all config values (API keys masked, returns `_set` boolean)
- `GET /api/settings` — all editable config values
- `POST /api/settings` — write fields to config.py, reload config
- `POST /api/mode` — live-switch display mode
- `GET /api/wifi/scan` — scan nearby SSIDs via `iwlist wlan0 scan`
- `POST /api/wifi/connect` — write `wpa_supplicant.conf`, trigger `wpa_cli reconfigure`
- `POST /api/restart` — restart `metroclock` systemd service
- `POST /api/reboot` — reboot the Pi

## Config Fields (editable via web UI)
`WMATA_API_KEY`, `WMATA_STATION_CODE`, `OPENWEATHER_API_KEY`, `OPENWEATHER_CITY_ID`, `WEATHER_UNITS`, `AVIATIONSTACK_API_KEY`, `FLIGHT_NUMBER`, `DISPLAY_MODE`, `MATRIX_BRIGHTNESS`, `WEB_SERVER_PORT`, `SETUP_MODE`

## Key APIs
- **WMATA**: `api.wmata.com/StationPrediction.svc/json/GetPrediction/{STATION_CODE}` (header: `api_key`)
- **OpenWeatherMap**: `api.openweathermap.org/data/2.5/weather?id={CITY_ID}&appid={KEY}&units={UNITS}`
- **AviationStack**: `api.aviationstack.com/v1/flights?access_key={KEY}&flight_iata={FLIGHT}`

## First-Boot / Etsy Flow
Pi has no WiFi → `setup_hotspot.sh` broadcasts `MetroClock-Setup` hotspot → customer connects → opens `192.168.4.1` → enters home WiFi + API keys → Pi reconnects to home network, ready to use.

## Conventions
- **Never commit without explicit user approval** — always leave changes unstaged or staged but not committed
- Do not modify `core/display.py` or widget files unless specifically asked
- Settings always written directly to `config.py` (no separate JSON config file)
- Web UI has no authentication (intentional — local network only)
- The brightness slider was intentionally removed from the web UI — do not add it back
- `CLAUDE.md` is in `.gitignore` — never commit it
