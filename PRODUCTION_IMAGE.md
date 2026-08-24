# MetroClock Production Image

This is the repeatable flow for creating a clean MetroClock SD card image for
test and early production units.

## What The Base Image Contains

- Raspberry Pi OS configured for Pi Zero 2 W
- repo checkout at `/home/zaid/metroclock`
- Python venv at `/home/zaid/metroclock/.venv`
- RGB matrix bindings built into the venv
- `metroclock.service`
- `metroclock-network-recovery.timer`
- `avahi-daemon` for `metroclock.local`
- setup hotspot support for `MetroClock-Setup`
- first-boot identity regeneration

## What The Base Image Must Not Contain

- your home Wi-Fi credentials
- a Supabase/cloud device token
- a pairing code
- a generated `/etc/metroclock/device_id`
- SSH host keys copied from the source device
- old logs or shell history

## Create A Clean Source SD Card

Start from a freshly flashed Raspberry Pi OS card. Use Raspberry Pi Imager:

- hostname: `metroclock`
- username: `zaid`
- enable SSH
- Wi-Fi country: `US`

You can temporarily add your Wi-Fi during initial setup so the Pi can download
dependencies. The production prep script removes saved Wi-Fi before capture.

SSH in, clone the repo, then run:

```bash
cd /home/zaid/metroclock
chmod +x scripts/setup_pi.sh
./scripts/setup_pi.sh
```

Apply the boot config changes from `SETUP_PI.md`, reboot, and verify:

```bash
cd /home/zaid/metroclock
./scripts/device_doctor.sh
curl -sS http://127.0.0.1/api/status | head -c 500; echo
```

## Prepare For Image Capture

Run this only when the source SD card is ready to become the reusable base:

```bash
cd /home/zaid/metroclock
./scripts/prepare_production_image.sh --yes --shutdown
```

The script stops services, clears device/user state, removes saved Wi-Fi,
removes SSH host keys, clears logs, installs a first-boot identity service, and
powers off the Pi.

Wait for the Pi activity light to settle before removing the SD card.

## Capture The SD Image On macOS

Insert the SD card into the Mac and identify it:

```bash
diskutil list
```

Unmount the disk, replacing `diskN` with the SD card disk:

```bash
diskutil unmountDisk /dev/diskN
```

Capture it:

```bash
sudo dd if=/dev/rdiskN of=metroclock-production-base.img bs=4m status=progress
sync
diskutil eject /dev/diskN
```

Compress it for storage:

```bash
gzip -9 metroclock-production-base.img
```

Name images with the app version and date, for example:

```text
metroclock-production-base-0.2.0-2026-08-23.img.gz
```

## Flash A Test Unit From The Image

Use Raspberry Pi Imager or `dd` to flash the captured image to a second SD card.
Boot it in a clock.

Expected first boot:

- unique machine id and SSH host keys are regenerated
- unique MetroClock device id is created
- `MetroClock-Setup` appears
- the matrix shows the app setup screen
- the iOS app can send home Wi-Fi and pair the clock
- Supabase shows a new device row

Verify on the Pi after pairing:

```bash
sudo test -s /etc/metroclock/device_id
sudo systemctl status metroclock --no-pager -l
curl -sS http://127.0.0.1/api/status | head -c 500; echo
```

## Important

Do not capture the current debug SD card without running the prep script. It has
real Wi-Fi, pairing, and debugging state that should not ship to anyone else.
