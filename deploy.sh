#!/bin/bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
TARGET_BRANCH="${1:-$CURRENT_BRANCH}"

echo "Deploying branch: ${TARGET_BRANCH}"
git fetch origin
git pull --ff-only origin "${TARGET_BRANCH}"

sudo systemctl restart metroclock
sudo systemctl status metroclock --no-pager

echo
echo "Recent logs:"
sudo journalctl -u metroclock -n 40 --no-pager

echo
echo "API status (first 500 chars):"
curl -sSf http://127.0.0.1/api/status | head -c 500
echo
