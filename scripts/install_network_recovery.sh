#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${METROCLOCK_REPO_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
SERVICE_NAME="${METROCLOCK_NETWORK_RECOVERY_SERVICE_NAME:-metroclock-network-recovery}"
SERVICE_PATH="${METROCLOCK_NETWORK_RECOVERY_SERVICE_PATH:-/etc/systemd/system/${SERVICE_NAME}.service}"
TIMER_PATH="${METROCLOCK_NETWORK_RECOVERY_TIMER_PATH:-/etc/systemd/system/${SERVICE_NAME}.timer}"
RECOVERY_SCRIPT="${METROCLOCK_RECOVERY_SCRIPT:-$REPO_DIR/scripts/network_recovery.sh}"

if [ ! -x "$RECOVERY_SCRIPT" ]; then
  echo "Missing executable recovery script: $RECOVERY_SCRIPT" >&2
  exit 1
fi

echo "Writing ${SERVICE_NAME}.service..."
sudo tee "$SERVICE_PATH" >/dev/null <<EOF
[Unit]
Description=MetroClock independent network recovery
After=network.target

[Service]
Type=oneshot
ExecStart=$RECOVERY_SCRIPT check
EnvironmentFile=-/etc/metroclock/secrets.env
EOF

echo "Writing ${SERVICE_NAME}.timer..."
sudo tee "$TIMER_PATH" >/dev/null <<EOF
[Unit]
Description=Run MetroClock network recovery after boot and periodically

[Timer]
OnBootSec=75
OnUnitActiveSec=120
AccuracySec=15
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now "${SERVICE_NAME}.timer"

echo "Installed ${SERVICE_NAME}.timer"
