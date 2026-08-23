#!/usr/bin/env bash
set -uo pipefail

SERVICE_NAME="${METROCLOCK_SERVICE_NAME:-metroclock}"
RECOVERY_SERVICE_NAME="${METROCLOCK_NETWORK_RECOVERY_SERVICE_NAME:-metroclock-network-recovery}"
HEALTH_URL="${METROCLOCK_HEALTH_URL:-http://127.0.0.1/api/status}"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

failures=0

section() {
  printf '\n== %s ==\n' "$*"
}

run() {
  printf '\n$ %s\n' "$*"
  "$@"
  local status=$?
  if [ "$status" -ne 0 ]; then
    printf 'command failed: exit %s\n' "$status"
  fi
  return "$status"
}

check() {
  local label="$1"
  shift
  printf '%-42s' "$label"
  if "$@" >/tmp/metroclock-doctor-check.out 2>&1; then
    printf 'OK\n'
  else
    printf 'FAIL\n'
    sed 's/^/  /' /tmp/metroclock-doctor-check.out
    failures=$((failures + 1))
  fi
}

have() {
  command -v "$1" >/dev/null 2>&1
}

section "Identity"
run date
run hostname
run uname -a
run uptime

section "Repo"
if [ -d "$REPO_DIR/.git" ]; then
  run git -C "$REPO_DIR" branch --show-current
  run git -C "$REPO_DIR" describe --tags --always --dirty
  run git -C "$REPO_DIR" status --short
else
  echo "No git checkout at $REPO_DIR"
  failures=$((failures + 1))
fi

section "Critical Checks"
check "systemd is available" have systemctl
check "${SERVICE_NAME}.service active" systemctl is-active --quiet "$SERVICE_NAME"
check "${RECOVERY_SERVICE_NAME}.timer active" systemctl is-active --quiet "${RECOVERY_SERVICE_NAME}.timer"
check "local API status" curl -fsS --max-time 5 "$HEALTH_URL"
check "local preview endpoint" curl -fsS --max-time 5 -I http://127.0.0.1/preview.png
check "runtime config exists" test -f /etc/metroclock/config.json
check "device id exists" test -f /etc/metroclock/device_id
check "enough free root disk" sh -c 'avail=$(df -Pk / | awk "NR==2 {print \$4}"); [ "${avail:-0}" -gt 524288 ]'

section "Network"
if have ip; then
  run ip addr
  run ip route
fi
if have iwgetid; then
  run iwgetid wlan0 -r
fi
if have systemctl; then
  run systemctl status avahi-daemon --no-pager -l
  run systemctl status hostapd dnsmasq --no-pager -l
  run systemctl status "${RECOVERY_SERVICE_NAME}.timer" --no-pager -l
fi

section "MetroClock Service"
if have systemctl; then
  run systemctl status "$SERVICE_NAME" --no-pager -l
fi
if have journalctl; then
  run journalctl -u "$SERVICE_NAME" -b -n 200 --no-pager
  run journalctl -u "$RECOVERY_SERVICE_NAME" -b -n 120 --no-pager
fi

section "Local API"
run curl -fsS --max-time 5 "$HEALTH_URL"
run curl -fsS --max-time 5 -I http://127.0.0.1/preview.png

section "System Health"
run df -h
run free -h
if have vcgencmd; then
  run vcgencmd measure_temp
  run vcgencmd get_throttled
fi
run dmesg -T

section "Result"
if [ "$failures" -eq 0 ]; then
  echo "MetroClock doctor passed."
  exit 0
fi

echo "MetroClock doctor found ${failures} failing check(s)."
exit 1
