#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[1/3] Installing hotspot dependencies..."
sudo apt-get update -qq
sudo apt-get install -y hostapd dnsmasq wireless-tools

echo "[2/3] Marking MetroClock setup mode..."
python3 - <<EOF || true
import sys

sys.path.insert(0, "${APP_DIR}")
import config_manager

config_manager.write_config({"SETUP_MODE": True})
EOF

echo "[3/3] Starting recovery hotspot..."
sudo "$APP_DIR/scripts/network_recovery.sh" start-hotspot

echo "Done. Connect to 'MetroClock-Setup'."
echo "If MetroClock is running, open http://192.168.4.1"
echo "If the app is down, SSH with: ssh zaid@192.168.4.1"
