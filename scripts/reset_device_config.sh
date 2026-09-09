#!/usr/bin/env bash
# Reset the runtime config to factory state.
#
# Writes a fresh /etc/metroclock/config.json containing only the deliberate
# image defaults. Everything else is omitted on purpose, so config.py supplies
# it — config.py is the version-controlled source of truth for defaults, and
# seeding from whatever happened to be on the build unit made "the developer's
# settings" a second, invisible one.
#
# Shipped API keys are read from the environment so they are never committed:
#
#   METROCLOCK_IMAGE_OPENWEATHER_API_KEY=... \
#   METROCLOCK_IMAGE_WMATA_API_KEY=... \
#   METROCLOCK_IMAGE_AVIATIONSTACK_API_KEY=... \
#     scripts/reset_device_config.sh --yes
#
# Any key left unset is written empty, and its widget shows a placeholder
# explaining why rather than a blank panel.
#
# Clears: cloud pairing state and all personalisation (location, station, teams,
# symbols, colours, layout).
# Does NOT touch: Wi-Fi credentials, device id, SSH host keys — those belong to
# prepare_production_image.sh, which calls this script.
set -euo pipefail

CONFIG_PATH="${METROCLOCK_CONFIG_PATH:-/etc/metroclock/config.json}"
# `python3 -` has no __file__, so the repo root is resolved here and passed
# in as PYTHONPATH for the factory_defaults import below.
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RESTART=0
YES=0

usage() {
  cat <<USAGE
Usage:
  scripts/reset_device_config.sh --yes [--restart]

Options:
  --yes      Required. Confirms that runtime settings will be erased.
  --restart  Restart the metroclock service afterwards.

Environment:
  METROCLOCK_IMAGE_OPENWEATHER_API_KEY    baked into the image if set
  METROCLOCK_IMAGE_WMATA_API_KEY          baked into the image if set
  METROCLOCK_IMAGE_AVIATIONSTACK_API_KEY  baked into the image if set
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --yes) YES=1; shift ;;
    --restart) RESTART=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unexpected argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ "$YES" -ne 1 ]; then
  echo "Refusing to run without --yes: this erases all runtime settings." >&2
  usage >&2
  exit 2
fi

echo "Resetting $CONFIG_PATH to factory defaults..."

# Build the file as the invoking user, then install it as root. Running the
# generator under sudo would either drop the key environment (env_reset) or
# force the keys onto a command line, where they would be visible in ps.
tmp_prev="$(mktemp)"
tmp_new="$(mktemp)"
tmp_prov="$(mktemp)"
trap 'rm -f "$tmp_prev" "$tmp_new" "$tmp_prov"' EXIT
chmod 600 "$tmp_prev" "$tmp_new" "$tmp_prov"

if ! sudo cat "$CONFIG_PATH" > "$tmp_prev" 2>/dev/null; then
  printf '{}\n' > "$tmp_prev"
fi

PYTHONPATH="$REPO_ROOT" python3 - "$tmp_prev" "$tmp_new" "$tmp_prov" <<'PY'
import json
import sys

# Shared with core/power.py so an image build and a field factory reset cannot
# disagree about what "factory" means.
import factory_defaults

previous_path, out_path, provisioning_path = sys.argv[1], sys.argv[2], sys.argv[3]

try:
    with open(previous_path, "r", encoding="utf-8") as f:
        previous = json.load(f)
    if not isinstance(previous, dict):
        previous = {}
except Exception:
    previous = {}

# An image build takes provider keys from the environment; it never inherits
# whatever happened to be on the build unit.
data = factory_defaults.build()

cleared = factory_defaults.cleared_keys(previous)
if cleared:
    print("  cleared %d personalised setting(s): %s" % (len(cleared), ", ".join(cleared)))
else:
    print("  no personalised settings were present")

for setting, env_var in factory_defaults.SHIPPED_KEY_FIELDS.items():
    state = "set from %s" % env_var if data[setting] else "EMPTY (widget will show a placeholder)"
    print(f"  {setting}: {state}")

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, sort_keys=True)
    f.write("\n")

# Recorded separately so a field factory reset can restore the keys this image
# shipped with, rather than whatever key the user later typed into the app.
with open(provisioning_path, "w", encoding="utf-8") as f:
    json.dump(factory_defaults.provisioning_payload(data), f, indent=2, sort_keys=True)
    f.write("\n")
print(f"  wrote {len(data)} factory defaults")
PY

sudo mkdir -p "$(dirname "$CONFIG_PATH")"
sudo install -m 600 -o root -g root "$tmp_new" "$CONFIG_PATH"
sudo install -m 600 -o root -g root "$tmp_prov" "${METROCLOCK_PROVISIONING_PATH:-/etc/metroclock/provisioning.json}"

if [ "$RESTART" -eq 1 ]; then
  echo "Restarting metroclock..."
  sudo systemctl restart metroclock
fi

echo "Done. Everything not listed above now comes from config.py."
