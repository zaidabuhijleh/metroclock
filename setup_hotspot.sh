#!/bin/bash
set -e

CONFIG_FILE="/home/pi/metroclock/config.py"

echo "[1/6] Installing hostapd and dnsmasq..."
apt-get update -qq
apt-get install -y hostapd dnsmasq

echo "[2/6] Configuring static IP for wlan0..."
cat >> /etc/dhcpcd.conf <<'EOF'

# MetroClock hotspot
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
EOF

echo "[3/6] Configuring dnsmasq..."
mv /etc/dnsmasq.conf /etc/dnsmasq.conf.bak 2>/dev/null || true
cat > /etc/dnsmasq.conf <<'EOF'
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
# Captive portal: resolve all domains to the Pi
address=/#/192.168.4.1
EOF

echo "[4/6] Configuring hostapd..."
cat > /etc/hostapd/hostapd.conf <<'EOF'
interface=wlan0
driver=nl80211
ssid=MetroClock-Setup
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
EOF

# Point the hostapd default config to our file
sed -i 's|#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd

echo "[5/6] Enabling and starting services..."
systemctl unmask hostapd
systemctl enable hostapd dnsmasq
systemctl restart dhcpcd
systemctl start hostapd dnsmasq

echo "[6/6] Setting SETUP_MODE = True in config.py..."
sed -i 's/^SETUP_MODE\s*=.*/SETUP_MODE = True/' "$CONFIG_FILE"

echo "Done. Connect to the 'MetroClock-Setup' WiFi network and open http://192.168.4.1"
