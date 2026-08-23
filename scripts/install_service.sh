#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${METROCLOCK_VENV_DIR:-$REPO_DIR/.venv}"
SERVICE_NAME="${METROCLOCK_SERVICE_NAME:-metroclock}"
SERVICE_PATH="${METROCLOCK_SERVICE_PATH:-/etc/systemd/system/${SERVICE_NAME}.service}"
CONFIG_PATH="${METROCLOCK_CONFIG_PATH:-/etc/metroclock/config.json}"
SECRETS_PATH="${METROCLOCK_SECRETS_PATH:-/etc/metroclock/secrets.env}"

if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "Missing Python executable: $VENV_DIR/bin/python" >&2
  echo "Run scripts/setup_pi.sh first, or set METROCLOCK_VENV_DIR." >&2
  exit 1
fi

echo "Writing ${SERVICE_NAME} systemd service to ${SERVICE_PATH}..."
sudo tee "$SERVICE_PATH" >/dev/null <<EOF
[Unit]
Description=MetroClock LED Display
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$REPO_DIR
ExecStart=$VENV_DIR/bin/python $REPO_DIR/main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=METROCLOCK_CONFIG_PATH=$CONFIG_PATH
EnvironmentFile=-$SECRETS_PATH

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload

echo "Installed ${SERVICE_NAME}.service"
