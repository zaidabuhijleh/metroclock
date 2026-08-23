#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_NAME="${METROCLOCK_SERVICE_NAME:-metroclock}"
VENV_DIR="${METROCLOCK_VENV_DIR:-$REPO_DIR/.venv}"
STATE_DIR="${METROCLOCK_STATE_DIR:-/etc/metroclock}"
HEALTH_URL="${METROCLOCK_HEALTH_URL:-http://127.0.0.1/api/status}"
HEALTH_TIMEOUT_SECONDS="${METROCLOCK_HEALTH_TIMEOUT_SECONDS:-30}"
BOOTSTRAP_PERSIST_DIR="${METROCLOCK_UPDATE_BOOTSTRAP_DIR:-/etc/metroclock/update-bootstrap}"

TARGET_REF=""
ROLLBACK=0
SKIP_DEPS=0
SKIP_SERVICE_INSTALL=0
SKIP_NETWORK_RECOVERY_INSTALL=0
NO_RESTART=0

usage() {
  cat <<USAGE
Usage:
  scripts/update_pi.sh [--ref <branch|tag|sha>] [--skip-deps] [--skip-service-install] [--skip-network-recovery-install] [--no-restart]
  scripts/update_pi.sh --rollback

Examples:
  scripts/update_pi.sh --ref main
  scripts/update_pi.sh --ref v0.2.0-alpha
  scripts/update_pi.sh --rollback

If --ref is omitted, the current branch is updated from origin/<current-branch>.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --ref)
      TARGET_REF="${2:-}"
      if [ -z "$TARGET_REF" ]; then
        echo "--ref requires a value" >&2
        exit 2
      fi
      shift 2
      ;;
    --rollback)
      ROLLBACK=1
      shift
      ;;
    --skip-deps)
      SKIP_DEPS=1
      shift
      ;;
    --skip-service-install)
      SKIP_SERVICE_INSTALL=1
      shift
      ;;
    --skip-network-recovery-install)
      SKIP_NETWORK_RECOVERY_INSTALL=1
      shift
      ;;
    --no-restart)
      NO_RESTART=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [ -z "$TARGET_REF" ]; then
        TARGET_REF="$1"
        shift
      else
        echo "Unexpected argument: $1" >&2
        usage >&2
        exit 2
      fi
      ;;
  esac
done

cd "$REPO_DIR"

ensure_existing_pi_environment() {
  if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "Missing production Python environment: $VENV_DIR/bin/python" >&2
    echo "Run scripts/setup_pi.sh first. update_pi.sh only updates an already prepared Pi." >&2
    exit 1
  fi

  if ! "$VENV_DIR/bin/python" - <<'PY' >/dev/null 2>&1
from rgbmatrix import RGBMatrix, RGBMatrixOptions
PY
  then
    echo "Existing Python environment is missing rgbmatrix." >&2
    echo "Run scripts/setup_pi.sh first so the LED matrix bindings are built into the venv." >&2
    exit 1
  fi
}

if [ "$ROLLBACK" -eq 1 ]; then
  if [ -n "$TARGET_REF" ]; then
    echo "--rollback cannot be combined with --ref" >&2
    exit 2
  fi
  if [ ! -f "$STATE_DIR/previous_ref" ]; then
    echo "No rollback ref found at $STATE_DIR/previous_ref" >&2
    exit 1
  fi
  TARGET_REF="$(sudo cat "$STATE_DIR/previous_ref")"
  echo "Rolling back to previous ref: $TARGET_REF"
fi

if [ -z "$TARGET_REF" ]; then
  CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  if [ "$CURRENT_BRANCH" = "HEAD" ]; then
    echo "Detached HEAD; pass --ref <branch|tag|sha> explicitly." >&2
    exit 2
  fi
  TARGET_REF="$CURRENT_BRANCH"
fi

if [ -n "$(git status --porcelain)" ] && [ "${METROCLOCK_UPDATE_ALLOW_DIRTY:-0}" != "1" ]; then
  echo "Working tree is dirty. Commit/stash changes or set METROCLOCK_UPDATE_ALLOW_DIRTY=1." >&2
  git status --short >&2
  exit 1
fi

if [ "$SKIP_DEPS" -eq 0 ] || [ "$SKIP_SERVICE_INSTALL" -eq 0 ] || [ "$NO_RESTART" -eq 0 ]; then
  ensure_existing_pi_environment
fi

BEFORE_SHA="$(git rev-parse --verify HEAD)"
BEFORE_DESCRIBE="$(git describe --tags --always --dirty 2>/dev/null || git rev-parse --short HEAD)"
BOOTSTRAP_DIR="$(mktemp -d /tmp/metroclock-update.XXXXXX)"
trap 'rm -rf "$BOOTSTRAP_DIR"' EXIT
mkdir -p "$BOOTSTRAP_DIR/scripts"
for helper in install_service.sh install_network_recovery.sh network_recovery.sh; do
  if [ -f "$REPO_DIR/scripts/$helper" ]; then
    cp "$REPO_DIR/scripts/$helper" "$BOOTSTRAP_DIR/scripts/$helper"
    chmod +x "$BOOTSTRAP_DIR/scripts/$helper"
  fi
done

helper_script() {
  local helper="$1"
  if [ -x "$REPO_DIR/scripts/$helper" ]; then
    printf '%s\n' "$REPO_DIR/scripts/$helper"
    return 0
  fi
  if [ -x "$BOOTSTRAP_DIR/scripts/$helper" ]; then
    printf '%s\n' "$BOOTSTRAP_DIR/scripts/$helper"
    return 0
  fi
  echo "Missing update helper: $helper" >&2
  return 1
}

persist_bootstrap_helper() {
  local helper="$1"
  local source_path
  source_path="$(helper_script "$helper")"
  sudo mkdir -p "$BOOTSTRAP_PERSIST_DIR/scripts"
  sudo install -m 755 "$source_path" "$BOOTSTRAP_PERSIST_DIR/scripts/$helper"
  printf '%s\n' "$BOOTSTRAP_PERSIST_DIR/scripts/$helper"
}

echo "Current version: $BEFORE_DESCRIBE ($BEFORE_SHA)"
echo "Fetching origin..."
git fetch --tags origin

if git rev-parse --verify --quiet "refs/remotes/origin/${TARGET_REF}" >/dev/null; then
  echo "Checking out branch origin/${TARGET_REF}..."
  git checkout -B "$TARGET_REF" "origin/$TARGET_REF"
else
  echo "Checking out ref ${TARGET_REF}..."
  git checkout --detach "$TARGET_REF"
fi

AFTER_SHA="$(git rev-parse --verify HEAD)"
AFTER_DESCRIBE="$(git describe --tags --always --dirty 2>/dev/null || git rev-parse --short HEAD)"
echo "Updated to: $AFTER_DESCRIBE ($AFTER_SHA)"

if [ "$SKIP_DEPS" -eq 0 ]; then
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  echo "Installing Python requirements..."
  python -m pip install --upgrade pip setuptools wheel
  python -m pip install -r "$REPO_DIR/requirements.txt"
fi

if [ "$SKIP_SERVICE_INSTALL" -eq 0 ]; then
  METROCLOCK_REPO_DIR="$REPO_DIR" "$(helper_script install_service.sh)"
fi

if [ "$SKIP_NETWORK_RECOVERY_INSTALL" -eq 0 ]; then
  RECOVERY_SCRIPT="$REPO_DIR/scripts/network_recovery.sh"
  if [ ! -x "$RECOVERY_SCRIPT" ]; then
    RECOVERY_SCRIPT="$(persist_bootstrap_helper network_recovery.sh)"
  fi
  METROCLOCK_REPO_DIR="$REPO_DIR" METROCLOCK_RECOVERY_SCRIPT="$RECOVERY_SCRIPT" "$(helper_script install_network_recovery.sh)"
fi

sudo mkdir -p "$STATE_DIR"
printf '%s\n' "$BEFORE_SHA" | sudo tee "$STATE_DIR/previous_ref" >/dev/null
printf '%s\n' "$AFTER_SHA" | sudo tee "$STATE_DIR/current_ref" >/dev/null
printf '%s\n' "$AFTER_DESCRIBE" | sudo tee "$STATE_DIR/current_version" >/dev/null

if [ "$NO_RESTART" -eq 1 ]; then
  echo "Update staged without restart."
  exit 0
fi

echo "Restarting ${SERVICE_NAME}..."
sudo systemctl restart "$SERVICE_NAME"

echo "Waiting for health check: $HEALTH_URL"
deadline=$((SECONDS + HEALTH_TIMEOUT_SECONDS))
until curl -fsS --max-time 2 "$HEALTH_URL" >/tmp/metroclock-health.json; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "Health check failed after ${HEALTH_TIMEOUT_SECONDS}s." >&2
    echo "Recent ${SERVICE_NAME} logs:" >&2
    sudo journalctl -u "$SERVICE_NAME" -n 80 --no-pager >&2 || true
    exit 1
  fi
  sleep 2
done

echo "Health check passed."
echo "API status (first 500 chars):"
head -c 500 /tmp/metroclock-health.json
echo

echo
echo "Service status:"
sudo systemctl status "$SERVICE_NAME" --no-pager -l || true

echo
echo "Recent logs:"
sudo journalctl -u "$SERVICE_NAME" -n 40 --no-pager || true
