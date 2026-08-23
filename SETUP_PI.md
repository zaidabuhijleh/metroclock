# MetroClock Pi Setup

This is the canonical setup flow for a fresh Raspberry Pi OS install.

## 1) Flash + First Boot

Use Raspberry Pi Imager and set:
- Hostname: `metroclock`
- Enable SSH
- Username: `zaid`
- Wi-Fi SSID/password
- Wi-Fi country: `US`

Boot the Pi and SSH in.

## 2) Run Automated Setup

From repo root:

```bash
chmod +x scripts/setup_pi.sh
./scripts/setup_pi.sh
```

This script:
- installs system dependencies
- creates `.venv`
- installs Python requirements
- clones/builds `rpi-rgb-led-matrix` into the venv
- applies known fix for `Imaging.h`
- writes/enables `metroclock.service` with `scripts/install_service.sh`
- installs `metroclock-network-recovery.timer`
- prepares `/etc/metroclock/config.json`
- installs `hostapd`/`dnsmasq` for setup mode and `avahi-daemon` for `metroclock.local`

## 3) Set Boot Config Flags

These are intentionally manual because they modify boot files.

### `/boot/firmware/cmdline.txt`

Keep this file as a single line and append:

`isolcpus=3`

### `/boot/firmware/config.txt`

Ensure this line exists:

`dtparam=audio=off`

Reboot:

```bash
sudo reboot
```

## 4) Add API Keys

Edit runtime config (outside repo, survives `git pull`):

```bash
sudo nano /etc/metroclock/config.json
```

Add:

```json
{
  "WMATA_API_KEY": "YOUR_WMATA_KEY",
  "OPENWEATHER_API_KEY": "YOUR_OPENWEATHER_KEY"
}
```

Restart service:

```bash
sudo systemctl restart metroclock
```

## 5) Verify

```bash
sudo systemctl status metroclock --no-pager -l
curl -sS http://127.0.0.1/api/status | head -c 500; echo
```

The Wi-Fi setup manager keeps monitoring after boot. If saved Wi-Fi drops, it
starts `MetroClock-Setup`, then retries saved Wi-Fi every
`WIFI_SETUP_RETRY_SECONDS` seconds so late phone hotspots can recover without a
power-cycle.

## 6) Production Updates

Once a device is acting as a beta/production unit, update it through the
official update script instead of ad-hoc `git pull` commands:

```bash
cd /home/zaid/metroclock
./scripts/update_pi.sh --ref startup
```

For the full release/update checklist, see `PRODUCTION_UPDATES.md`.

## Recovery Hotspot

Setup Wi-Fi is no longer only an app feature. `scripts/setup_pi.sh` installs
`metroclock-network-recovery.timer`, which runs outside the MetroClock Python
app. If the Pi cannot join saved Wi-Fi after boot, it starts:

- SSID: `MetroClock-Setup`
- IP: `192.168.4.1`

When connected to that hotspot:

```bash
ssh zaid@192.168.4.1
```

If the MetroClock app is also running, the web UI should be available at:

```text
http://192.168.4.1
```
