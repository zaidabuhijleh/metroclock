#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_PATH="${METROCLOCK_CONFIG_PATH:-/etc/metroclock/config.json}"
SECRETS_PATH="${METROCLOCK_SECRETS_PATH:-/etc/metroclock/secrets.env}"
DEVICE_ID_PATH="${METROCLOCK_DEVICE_ID_PATH:-/etc/metroclock/device_id}"
WPA_SUPPLICANT_CONF="${METROCLOCK_WPA_SUPPLICANT_CONF:-/etc/wpa_supplicant/wpa_supplicant.conf}"
# Raspberry Pi Imager writes Wi-Fi credentials here, and cloud-init replays them
# on first boot — which silently undoes the Wi-Fi scrub below.
BOOT_DIRS="${METROCLOCK_BOOT_DIRS:-/boot/firmware /boot}"
HOSTNAME="${METROCLOCK_IMAGE_HOSTNAME:-metroclock}"
HOTSPOT_PASSWORD="${METROCLOCK_DEFAULT_SETUP_HOTSPOT_PASSWORD:-metroclock}"
SHUTDOWN=0
YES=0

usage() {
  cat <<USAGE
Usage:
  scripts/prepare_production_image.sh --yes [--shutdown]

Prepares this Pi/SD card to be captured as a reusable MetroClock production
base image. Run this only after scripts/setup_pi.sh has completed successfully.

This script intentionally removes device/user state:
- saved Wi-Fi credentials
- cloud token and pairing code
- generated MetroClock device id
- SSH host keys
- machine id
- logs and shell history

Options:
  --yes       Required safety confirmation.
  --shutdown  Power off at the end so the SD card can be removed and imaged.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --yes)
      YES=1
      shift
      ;;
    --shutdown)
      SHUTDOWN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unexpected argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ "$YES" -ne 1 ]; then
  usage >&2
  echo >&2
  echo "Refusing to continue without --yes." >&2
  exit 2
fi

if [ "$(uname -s)" != "Linux" ]; then
  echo "This script must run on the Raspberry Pi image source device." >&2
  exit 1
fi

echo "[1/10] Stopping MetroClock services..."
sudo systemctl stop metroclock 2>/dev/null || true
sudo systemctl stop metroclock-network-recovery.timer 2>/dev/null || true
sudo systemctl stop metroclock-network-recovery.service 2>/dev/null || true
sudo systemctl stop hostapd 2>/dev/null || true
sudo systemctl stop dnsmasq 2>/dev/null || true

echo "[2/10] Refreshing installed services..."
"$REPO_DIR/scripts/install_service.sh"
"$REPO_DIR/scripts/install_network_recovery.sh"
sudo systemctl stop metroclock-network-recovery.timer 2>/dev/null || true
sudo systemctl stop metroclock-network-recovery.service 2>/dev/null || true
sudo systemctl enable metroclock
sudo systemctl enable avahi-daemon 2>/dev/null || true

echo "[3/10] Writing clean runtime config..."
sudo mkdir -p "$(dirname "$CONFIG_PATH")" "$(dirname "$SECRETS_PATH")"
sudo python3 - "$CONFIG_PATH" <<'PY'
import json
import os
import sys

path = sys.argv[1]
data = {}
try:
    with open(path, "r", encoding="utf-8") as f:
        existing = json.load(f)
    if isinstance(existing, dict):
        data.update(existing)
except Exception:
    pass

data.update(
    {
        "DISPLAY_MODE": "clock",
        "CLOCK_SHOW_AMPM": False,
        "CLOCK_SHOW_DATE": False,
        "SETUP_MODE": False,
        "WIFI_SETUP_ENABLED": True,
        "WIFI_SETUP_FORCE_HOTSPOT_UNPAIRED": True,
        "WIFI_SETUP_HOTSPOT_SSID": "MetroClock-Setup",
        "WIFI_SETUP_HOTSPOT_IP": "192.168.4.1",
        "WIFI_SETUP_HOTSPOT_PASSWORD": "metroclock",
        "METROCLOCK_CLOUD_ENABLED": False,
        "METROCLOCK_CLOUD_BASE_URL": "",
        "METROCLOCK_CLOUD_DEVICE_TOKEN": "",
        "METROCLOCK_CLOUD_PAIRING_CODE": "",
    }
)

for key in (
    "WMATA_API_KEY",
    "OPENWEATHER_API_KEY",
    "AVIATIONSTACK_API_KEY",
):
    data[key] = ""

os.makedirs(os.path.dirname(path), exist_ok=True)
tmp_path = path + ".tmp"
with open(tmp_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, sort_keys=True)
    f.write("\n")
os.replace(tmp_path, path)
PY
sudo chmod 600 "$CONFIG_PATH"

echo "[4/10] Writing production secrets defaults..."
sudo install -m 600 /dev/null "$SECRETS_PATH"
printf 'METROCLOCK_WIFI_SETUP_HOTSPOT_PASSWORD=%s\n' "$HOTSPOT_PASSWORD" | sudo tee "$SECRETS_PATH" >/dev/null
sudo chmod 600 "$SECRETS_PATH"

echo "[5/10] Clearing saved Wi-Fi credentials..."
sudo tee "$WPA_SUPPLICANT_CONF" >/dev/null <<'EOF'
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

EOF
sudo chmod 600 "$WPA_SUPPLICANT_CONF"
if command -v nmcli >/dev/null 2>&1; then
  while IFS= read -r connection; do
    [ -n "$connection" ] || continue
    sudo nmcli connection delete "$connection" >/dev/null 2>&1 || true
  done < <(nmcli -t -f NAME,TYPE connection show | awk -F: '$2 == "wifi" { print $1 }')
fi
sudo find /etc/NetworkManager/system-connections -type f -name '*.nmconnection' -delete 2>/dev/null || true

# netplan renders NM wifi profiles to /etc/netplan/90-NM-<uuid>.yaml, which holds
# the SSID and PSK. Deleting the NM profile usually removes it, but not always,
# and the find above never touches it.
for netplan_file in /etc/netplan/*.yaml; do
  [ -f "$netplan_file" ] || continue
  if sudo grep -qs 'access-points' "$netplan_file"; then
    sudo rm -f "$netplan_file"
  fi
done

# Boot-partition provisioning. Without this the credentials come back on the
# next boot, which is exactly how a "scrubbed" image kept rejoining a home
# network and masked the fact that app onboarding never ran.
for boot_dir in $BOOT_DIRS; do
  [ -d "$boot_dir" ] || continue
  sudo rm -f "$boot_dir/network-config" 2>/dev/null || true
done

# cloud-init caches the datasource, including the network config it was given.
sudo rm -f /var/lib/cloud/instances/*/network-config* 2>/dev/null || true
sudo rm -f /var/lib/cloud/instance/network-config* 2>/dev/null || true
sudo rm -f /var/lib/cloud/seed/nocloud*/network-config 2>/dev/null || true

echo "[6/10] Clearing unit-specific identity..."
sudo rm -f "$DEVICE_ID_PATH"
sudo truncate -s 0 /etc/machine-id 2>/dev/null || true
sudo rm -f /var/lib/dbus/machine-id 2>/dev/null || true
sudo rm -f /etc/ssh/ssh_host_* 2>/dev/null || true

echo "[7/10] Setting hostname..."
printf '%s\n' "$HOSTNAME" | sudo tee /etc/hostname >/dev/null
if [ -f /etc/hosts ]; then
  sudo sed -i "s/127\\.0\\.1\\.1.*/127.0.1.1\t${HOSTNAME}/" /etc/hosts
fi

echo "[8/10] Cleaning logs, caches, and shell history..."
sudo journalctl --rotate >/dev/null 2>&1 || true
sudo journalctl --vacuum-time=1s >/dev/null 2>&1 || true
sudo rm -rf /var/log/*.gz /var/log/*.[0-9] /var/log/journal/* 2>/dev/null || true
sudo rm -rf /tmp/* /var/tmp/* 2>/dev/null || true
rm -f "$HOME/.bash_history" "$HOME/.zsh_history" 2>/dev/null || true
sudo rm -f /root/.bash_history /root/.zsh_history 2>/dev/null || true

echo "[9/10] Enabling first-boot services..."
sudo tee /etc/systemd/system/metroclock-first-boot.service >/dev/null <<EOF
[Unit]
Description=Regenerate MetroClock image identity on first boot
DefaultDependencies=no
Before=ssh.service sshd.service metroclock.service
After=local-fs.target

[Service]
Type=oneshot
ExecStart=$REPO_DIR/scripts/first_boot_identity.sh

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable metroclock-first-boot.service
sudo systemctl enable metroclock
sudo systemctl enable metroclock-network-recovery.timer
sudo systemctl enable ssh 2>/dev/null || sudo systemctl enable sshd 2>/dev/null || true

echo "[10/10] Verifying no credentials or identity survived..."
LEAKS=0
report_leak() {
  LEAKS=$((LEAKS + 1))
  echo "  LEAK: $1" >&2
}

for boot_dir in $BOOT_DIRS; do
  [ -d "$boot_dir" ] || continue
  if [ -f "$boot_dir/network-config" ]; then
    report_leak "$boot_dir/network-config still present (Wi-Fi credentials)"
  fi
  if [ -f "$boot_dir/user-data" ] && sudo grep -qiE 'wifi|wpa|psk|ssid' "$boot_dir/user-data"; then
    report_leak "$boot_dir/user-data mentions Wi-Fi; remove those keys by hand"
  fi
done

if sudo grep -qs 'network={' "$WPA_SUPPLICANT_CONF"; then
  report_leak "$WPA_SUPPLICANT_CONF still contains a network block"
fi
if [ -f "$WPA_SUPPLICANT_CONF" ]; then
  wpa_mode="$(stat -c '%a' "$WPA_SUPPLICANT_CONF")"
  if [ "$wpa_mode" != "600" ]; then
    report_leak "$WPA_SUPPLICANT_CONF is mode $wpa_mode, expected 600"
  fi
fi

if sudo find /etc/NetworkManager/system-connections -type f -name '*.nmconnection' 2>/dev/null | grep -q .; then
  report_leak "NetworkManager connection profiles still present"
fi
if sudo grep -lqs 'access-points' /etc/netplan/*.yaml 2>/dev/null; then
  report_leak "a netplan file still defines wireless access-points"
fi
if [ -s "$DEVICE_ID_PATH" ]; then
  report_leak "$DEVICE_ID_PATH still present (unit identity)"
fi
if sudo grep -qs 'METROCLOCK_CLOUD_DEVICE_TOKEN"[[:space:]]*:[[:space:]]*"[^"]' "$CONFIG_PATH"; then
  report_leak "$CONFIG_PATH still holds a cloud device token"
fi
if sudo find /etc/ssh -maxdepth 1 -name 'ssh_host_*' 2>/dev/null | grep -q .; then
  report_leak "SSH host keys still present"
fi

if [ "$LEAKS" -gt 0 ]; then
  echo >&2
  echo "Image prep FAILED verification with $LEAKS problem(s)." >&2
  echo "Do NOT capture this card. Fix the items above and re-run this script." >&2
  exit 1
fi
echo "  clean"

sync

echo
echo "MetroClock production image prep complete."
echo "The next boot should create a fresh device id and start MetroClock-Setup."
echo
if [ "$SHUTDOWN" -eq 1 ]; then
  echo "Shutting down now. Wait for activity LEDs to settle before removing the SD card."
  sudo shutdown -h now
else
  echo "Next step: sudo shutdown -h now, then capture the SD card image."
fi
