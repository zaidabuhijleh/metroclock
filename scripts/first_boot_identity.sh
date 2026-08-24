#!/usr/bin/env bash
set -euo pipefail

DEVICE_ID_PATH="${METROCLOCK_DEVICE_ID_PATH:-/etc/metroclock/device_id}"

if [ ! -s /etc/machine-id ] && command -v systemd-machine-id-setup >/dev/null 2>&1; then
  systemd-machine-id-setup
fi

if command -v ssh-keygen >/dev/null 2>&1; then
  ssh-keygen -A
fi

if [ ! -s "$DEVICE_ID_PATH" ]; then
  mkdir -p "$(dirname "$DEVICE_ID_PATH")"
  python3 - "$DEVICE_ID_PATH" <<'PY'
import os
import sys
import uuid

path = sys.argv[1]
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w", encoding="utf-8") as f:
    f.write(uuid.uuid4().hex + "\n")
PY
  chmod 600 "$DEVICE_ID_PATH"
fi

systemctl disable metroclock-first-boot.service >/dev/null 2>&1 || true
rm -f /etc/systemd/system/metroclock-first-boot.service
systemctl daemon-reload
