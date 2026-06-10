#!/bin/bash
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[1/3] Installing hotspot dependencies..."
apt-get update -qq
apt-get install -y hostapd dnsmasq

echo "[2/3] Marking MetroClock setup mode..."
python3 - <<EOF
import sys

sys.path.insert(0, "${APP_DIR}")
import config_manager

config_manager.write_config({"SETUP_MODE": True})
EOF

echo "[3/3] Restarting MetroClock..."
systemctl restart metroclock

echo "Done. MetroClock will start the 'MetroClock-Setup' fallback hotspot if it cannot join saved WiFi."
echo "Connect to that WiFi network and open http://192.168.4.1"
