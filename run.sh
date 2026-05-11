#!/bin/bash
set -e
cd "$(dirname "$0")"

python3 - <<EOF
import os
import config_manager

updates = {}
for key in ("WMATA_API_KEY", "OPENWEATHER_API_KEY", "AVIATIONSTACK_API_KEY"):
    value = os.getenv(key)
    if value:
        updates[key] = value

if updates:
    config_manager.write_config(updates)
EOF

exec python3 main.py
