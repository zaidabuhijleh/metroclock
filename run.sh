#!/bin/bash
set -e
cd "$(dirname "$0")"

WMATA_API_KEY=""
OPENWEATHER_API_KEY=""
AVIATIONSTACK_API_KEY=""

python3 - <<EOF
import config_manager
config_manager.write_config({
    "WMATA_API_KEY":        "$WMATA_API_KEY",
    "OPENWEATHER_API_KEY":  "$OPENWEATHER_API_KEY",
    "AVIATIONSTACK_API_KEY":"$AVIATIONSTACK_API_KEY",
})
EOF

exec python3 main.py
