# MetroClock Production Updates

This is the production update flow for the first beta/test units. It keeps the
Pi as a git checkout for now, but makes updates deliberate, versioned,
health-checked, and rollbackable.

## Production Device Contract

A production MetroClock device should have:

- repo checkout: `/home/zaid/metroclock`
- Python venv: `/home/zaid/metroclock/.venv`
- systemd service: `metroclock.service`
- recovery timer: `metroclock-network-recovery.timer`
- runtime config: `/etc/metroclock/config.json`
- secrets/env file: `/etc/metroclock/secrets.env`
- stable device id: `/etc/metroclock/device_id`

Runtime config and secrets live outside the repo so `git pull`, branch changes,
and tag rollbacks do not wipe user/device state.

## Channels

Use these conventions:

- `startup`: current hardware/product polish channel for the debug/beta device.
- `main`: production-ready integration branch.
- `vX.Y.Z` or `vX.Y.Z-alpha`: pinned release tags for devices you do not want
  drifting with a branch.

For the first productionized debug unit, update from `startup` until the launch
flow is merged to `main`. For friend/beta units, prefer pinned release tags.

## Promote The Debug Device

Use this flow for the device that has been acting as the debug unit.

If the device is not reachable over Wi-Fi, connect it by Ethernet first. For a
Pi Zero 2 W, that means:

- power cable stays in `PWR IN`
- micro-USB OTG adapter goes into the `USB` port
- USB Ethernet adapter plugs into the OTG adapter
- Ethernet cable goes from the adapter to the router

Then find the Pi through your router or a LAN scan and SSH in. If networking is
still unavailable, use mini-HDMI plus a USB keyboard.

On the Pi, start with diagnostics:

```bash
cd /home/zaid/metroclock
./scripts/device_doctor.sh
```

Then inspect any obvious failures and update through the official pipeline:

```bash
cd /home/zaid/metroclock
git status --short
```

If the device was not installed with the current venv-backed setup flow, run:

```bash
./scripts/setup_pi.sh
```

Then update through the official pipeline:

```bash
./scripts/update_pi.sh --ref startup
```

Run the doctor again after update:

```bash
./scripts/device_doctor.sh
```

Verify locally:

```bash
curl -sS http://127.0.0.1/api/status | head -c 500; echo
sudo systemctl status metroclock --no-pager -l
```

Verify from your Mac when on the same network:

```bash
curl -sS http://metroclock.local/api/status | head -c 500; echo
```

## Normal Update Flow

1. Make code changes on a feature branch.
2. Validate locally/emulator where possible.
3. Merge to the target branch (`startup` for this beta device, `main` for
   production).
4. SSH to the Pi.
5. Run:

```bash
cd /home/zaid/metroclock
./scripts/update_pi.sh --ref startup
```

For a release tag:

```bash
./scripts/update_pi.sh --ref v0.2.0-alpha
```

The update script:

- refuses to run over uncommitted local changes
- fetches branches and tags from origin
- checks out the requested branch/tag/sha
- syncs Python requirements into `.venv`
- refreshes the systemd service definition
- refreshes the independent network recovery timer
- records current/previous refs in `/etc/metroclock`
- restarts `metroclock`
- waits for `/api/status`
- prints service status and recent logs

## Rollback

If an update starts but the product behavior is wrong:

```bash
cd /home/zaid/metroclock
./scripts/update_pi.sh --rollback
```

Rollback uses `/etc/metroclock/previous_ref`, reinstalls dependencies for that
checkout, restarts the service, and runs the same health check.

## Release Automation

The current GitHub workflow is `.github/workflows/release-please.yml`, but it is
a custom `version-tag` job despite the filename. On pushes to `main`, or manual
workflow dispatch, it computes the next tag from:

- `MASTER_BUILD_NUMBER`, for example `1.0`
- `IS_RELEASE`, either `true` for stable or `false` for alpha

It creates a tag like `v1.0.3` or `v1.0.3-alpha` and opens a GitHub release for
that tag.

## Before Sending Devices To Friends

- Run one update through `scripts/update_pi.sh` on the debug device.
- Run `scripts/device_doctor.sh` and fix every failing critical check.
- Confirm `/api/status` reports the expected `app_version`.
- Confirm cloud pairing still works after restart.
- Confirm local control still works at `metroclock.local`.
- Confirm preview endpoints still work: `/preview.png` and `/preview.pngstream`.
- Confirm `metroclock-network-recovery.timer` is installed and active.
- Confirm the physical display survives at least one restart and one reboot.
- Confirm a simulated Wi-Fi failure exposes `MetroClock-Setup` without relying
  on the MetroClock app process.

## Recovery When The App Is Down

The setup hotspot must not depend on the MetroClock app being healthy.
`metroclock-network-recovery.timer` runs `scripts/network_recovery.sh check`
outside the Python process. If saved Wi-Fi is unavailable, it starts
`MetroClock-Setup` at `192.168.4.1`.

Manual recovery command on the Pi:

```bash
sudo /home/zaid/metroclock/scripts/network_recovery.sh start-hotspot
```

Then connect to `MetroClock-Setup` and SSH:

```bash
ssh zaid@192.168.4.1
```
