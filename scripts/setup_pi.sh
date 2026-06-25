#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$REPO_DIR/.venv"
RGB_DIR="/home/zaid/rpi-rgb-led-matrix"
TMP_BUILD_DIR="/home/zaid"
SERVICE_PATH="/etc/systemd/system/metroclock.service"

echo "[1/8] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
  git \
  python3-venv \
  python3-pip \
  python3-dev \
  hostapd \
  dnsmasq \
  wireless-tools \
  build-essential \
  cmake \
  ninja-build \
  pkg-config \
  cython3 \
  python3-pil \
  libjpeg-dev \
  zlib1g-dev

echo "[2/8] Creating Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip setuptools wheel

echo "[3/8] Installing MetroClock Python requirements..."
python -m pip install -r "$REPO_DIR/requirements.txt"

echo "[4/8] Cloning rpi-rgb-led-matrix source..."
rm -rf "$RGB_DIR"
git clone https://github.com/hzeller/rpi-rgb-led-matrix.git "$RGB_DIR"

echo "[5/8] Installing rpi-rgb-led-matrix into venv..."
PY_VER="$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
export CFLAGS="-I/usr/include/python${PY_VER} -I/usr/include/python${PY_VER}/PIL"
export CMAKE_BUILD_PARALLEL_LEVEL=1
export NINJAFLAGS=-j1
TMPDIR="$TMP_BUILD_DIR" python -m pip install --no-cache-dir --no-build-isolation -v "$RGB_DIR"

echo "[6/8] Verifying rgbmatrix import..."
python - <<'PY'
from rgbmatrix import RGBMatrix, RGBMatrixOptions
print("rgbmatrix ok")
PY

echo "[7/8] Writing systemd service..."
sudo tee "$SERVICE_PATH" >/dev/null <<EOF
[Unit]
Description=MetroClock LED Display
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$REPO_DIR
ExecStart=$VENV_DIR/bin/python $REPO_DIR/main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=METROCLOCK_CONFIG_PATH=/etc/metroclock/config.json
EnvironmentFile=-/etc/metroclock/secrets.env

[Install]
WantedBy=multi-user.target
EOF

echo "[8/8] Enabling and starting service..."
sudo mkdir -p /etc/metroclock
if [ ! -f /etc/metroclock/config.json ]; then
  echo '{}' | sudo tee /etc/metroclock/config.json >/dev/null
  sudo chmod 600 /etc/metroclock/config.json
fi
sudo systemctl daemon-reload
sudo systemctl enable metroclock
sudo systemctl restart metroclock

echo
echo "Setup complete."
echo "Next manual steps:"
echo "1) Add 'isolcpus=3' to /boot/firmware/cmdline.txt (single line)."
echo "2) Ensure 'dtparam=audio=off' exists in /boot/firmware/config.txt."
echo "3) Reboot: sudo reboot"
echo
echo "Service status:"
sudo systemctl status metroclock --no-pager -l || true
