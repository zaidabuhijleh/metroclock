#!/usr/bin/env bash
set -euo pipefail

INTERFACE="${METROCLOCK_WIFI_INTERFACE:-wlan0}"
HOTSPOT_SSID="${METROCLOCK_WIFI_HOTSPOT_SSID:-MetroClock-Setup}"
HOTSPOT_IP="${METROCLOCK_WIFI_HOTSPOT_IP:-192.168.4.1}"
HOTSPOT_CIDR="${METROCLOCK_WIFI_HOTSPOT_CIDR:-${HOTSPOT_IP}/24}"
CONNECT_WAIT_SECONDS="${METROCLOCK_WIFI_RECOVERY_WAIT_SECONDS:-60}"
HOSTAPD_CONF="${METROCLOCK_HOSTAPD_CONF:-/etc/hostapd/hostapd.conf}"
DNSMASQ_CONF="${METROCLOCK_DNSMASQ_CONF:-/etc/dnsmasq.d/metroclock-setup.conf}"
STATE_DIR="${METROCLOCK_STATE_DIR:-/etc/metroclock}"

log() {
  printf '[metroclock-network-recovery] %s\n' "$*"
}

have() {
  command -v "$1" >/dev/null 2>&1
}

run_optional() {
  "$@" >/dev/null 2>&1 || true
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root, for example: sudo $0 $*" >&2
    exit 1
  fi
}

interface_exists() {
  [ -d "/sys/class/net/${INTERFACE}" ]
}

interface_ipv4() {
  ip -4 -o addr show dev "$INTERFACE" 2>/dev/null \
    | awk '{print $4}' \
    | cut -d/ -f1 \
    | head -n1
}

current_ssid() {
  if have iwgetid; then
    iwgetid "$INTERFACE" -r 2>/dev/null || true
  fi
}

has_default_route() {
  ip route show default dev "$INTERFACE" 2>/dev/null | grep -q '^default '
}

hotspot_active() {
  have systemctl || return 1
  systemctl is-active --quiet hostapd || return 1
  [ "$(interface_ipv4)" = "$HOTSPOT_IP" ]
}

is_connected() {
  interface_exists || return 1
  local ip_addr
  ip_addr="$(interface_ipv4)"
  [ -n "$ip_addr" ] || return 1
  [ "$ip_addr" != "$HOTSPOT_IP" ] || return 1

  if have iwgetid; then
    [ -n "$(current_ssid)" ] || return 1
  fi
  has_default_route || return 1
}

write_file() {
  local path="$1"
  local mode="${2:-644}"
  local tmp
  tmp="${path}.tmp"
  cat >"$tmp"
  chmod "$mode" "$tmp"
  mv "$tmp" "$path"
}

ensure_hotspot_config() {
  have hostapd || { log "hostapd is missing"; exit 1; }
  have dnsmasq || { log "dnsmasq is missing"; exit 1; }
  have ip || { log "ip command is missing"; exit 1; }

  mkdir -p "$(dirname "$HOSTAPD_CONF")" "$(dirname "$DNSMASQ_CONF")" "$STATE_DIR"

  write_file "$HOSTAPD_CONF" 644 <<EOF
interface=$INTERFACE
driver=nl80211
ssid=$HOTSPOT_SSID
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
EOF

  write_file "$DNSMASQ_CONF" 644 <<EOF
interface=$INTERFACE
bind-dynamic
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
address=/#/$HOTSPOT_IP
EOF

  if [ -f /etc/default/hostapd ]; then
    if grep -q '^#\?DAEMON_CONF=' /etc/default/hostapd; then
      sed -i.bak "s|^#\\?DAEMON_CONF=.*|DAEMON_CONF=\"$HOSTAPD_CONF\"|" /etc/default/hostapd
    else
      printf '\nDAEMON_CONF="%s"\n' "$HOSTAPD_CONF" >>/etc/default/hostapd
    fi
  fi
}

stop_hotspot() {
  run_optional systemctl stop hostapd
  run_optional systemctl stop dnsmasq
  rm -f "$STATE_DIR/recovery_hotspot_active"
}

restart_wifi_client() {
  run_optional ip addr flush dev "$INTERFACE"
  run_optional ip link set "$INTERFACE" up
  run_optional systemctl restart NetworkManager
  run_optional systemctl restart wpa_supplicant
  run_optional systemctl restart "wpa_supplicant@${INTERFACE}"
  run_optional systemctl restart dhcpcd
  run_optional wpa_cli -i "$INTERFACE" reconfigure
}

start_hotspot() {
  require_root "$@"
  interface_exists || { log "$INTERFACE does not exist"; exit 1; }
  ensure_hotspot_config

  log "starting recovery hotspot ${HOTSPOT_SSID} at http://${HOTSPOT_IP}"
  run_optional systemctl stop NetworkManager
  run_optional systemctl stop wpa_supplicant
  run_optional systemctl stop "wpa_supplicant@${INTERFACE}"
  run_optional systemctl stop dhcpcd
  ip addr flush dev "$INTERFACE"
  ip addr add "$HOTSPOT_CIDR" dev "$INTERFACE"
  ip link set "$INTERFACE" up
  systemctl unmask hostapd >/dev/null 2>&1 || true
  systemctl restart dnsmasq
  systemctl restart hostapd
  printf '%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$STATE_DIR/recovery_hotspot_active"
  log "hotspot active; connect to ${HOTSPOT_SSID}, then use http://${HOTSPOT_IP} or ssh zaid@${HOTSPOT_IP}"
}

check_or_recover() {
  require_root "$@"
  if ! interface_exists; then
    log "$INTERFACE is missing; cannot recover WiFi"
    exit 0
  fi

  local deadline
  deadline=$((SECONDS + CONNECT_WAIT_SECONDS))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if is_connected; then
      log "connected to $(current_ssid || true) at $(interface_ipv4); hotspot not needed"
      stop_hotspot
      exit 0
    fi
    sleep 3
  done

  if is_connected; then
    log "connected to $(current_ssid || true) at $(interface_ipv4); hotspot not needed"
    stop_hotspot
    exit 0
  fi

  if hotspot_active; then
    log "recovery hotspot already active at http://${HOTSPOT_IP}"
    exit 0
  fi

  start_hotspot
}

status() {
  if is_connected; then
    log "connected ssid=$(current_ssid || true) ip=$(interface_ipv4)"
  elif hotspot_active; then
    log "hotspot active ssid=${HOTSPOT_SSID} ip=${HOTSPOT_IP}"
  else
    log "not connected and hotspot inactive"
  fi
}

case "${1:-check}" in
  check)
    check_or_recover
    ;;
  start-hotspot)
    start_hotspot
    ;;
  stop-hotspot)
    require_root "$@"
    stop_hotspot
    restart_wifi_client
    ;;
  status)
    status
    ;;
  *)
    echo "Usage: $0 [check|start-hotspot|stop-hotspot|status]" >&2
    exit 2
    ;;
esac
