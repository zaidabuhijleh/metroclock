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
- writes/enables `metroclock.service`
- prepares `/etc/metroclock/config.json`

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

