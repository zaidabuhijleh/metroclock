"""Device power and lifecycle actions.

Everything here except display sleep ends the process, so each action is
*scheduled* on a short delay rather than run inline. The caller has to finish
first: the cloud agent must acknowledge the command, or the local API must
answer the HTTP request, before the device goes away. Run inline, a reboot
would kill the process mid-acknowledgement, the cloud would never mark the
command done, and it would be redelivered on the next poll - a clock that
reboots forever.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from typing import Any, Callable, Optional

import config
import config_manager
import factory_defaults

# Long enough for an acknowledgement round trip on a slow link, short enough
# that a user does not think the button failed.
DEFAULT_ACTION_DELAY_SECONDS = 3.0

DEVICE_ID_PATH = "/etc/metroclock/device_id"
WPA_SUPPLICANT_PATH = "/etc/wpa_supplicant/wpa_supplicant.conf"

# Best effort only. A clock with no network still has to complete its own wipe.
DEREGISTER_TIMEOUT_SECONDS = 8

_lock = threading.Lock()
_pending: Optional[str] = None


# --------------------------------------------------------------- display sleep


def display_should_sleep() -> bool:
    return bool(getattr(config, "DISPLAY_SLEEP", False))


def set_display_sleep(asleep: bool) -> dict[str, Any]:
    """Put the panel to sleep or wake it.

    This only stops rendering. The web server and cloud agent keep running on
    their own threads, which is the whole point: a sleeping clock must still be
    reachable, or there would be no way to wake it again.
    """
    changed = config_manager.write_config({"DISPLAY_SLEEP": bool(asleep)})
    return {"ok": True, "display_sleep": bool(asleep), "changed": list(changed.keys())}


# ------------------------------------------------------------------ scheduling


def pending_action() -> Optional[str]:
    with _lock:
        return _pending


def _clear_pending() -> None:
    global _pending
    with _lock:
        _pending = None


def schedule(action: str, delay: float = DEFAULT_ACTION_DELAY_SECONDS) -> dict[str, Any]:
    """Queue a power action to run shortly after the caller has replied."""
    global _pending

    handler = _ACTIONS.get(action)
    if handler is None:
        raise ValueError(f"Unsupported power action: {action}")

    with _lock:
        if _pending is not None:
            # First one wins. A reboot queued behind a factory reset would cut
            # the wipe short and leave the device half-reset.
            return {"ok": False, "error": f"{_pending} is already in progress"}
        _pending = action

    threading.Thread(
        target=_run_after,
        args=(handler, float(delay), action),
        name=f"power-{action}",
        daemon=True,
    ).start()
    return {"ok": True, "scheduled": action, "in_seconds": float(delay)}


def _run_after(handler: Callable[[], None], delay: float, action: str) -> None:
    time.sleep(max(0.0, delay))
    try:
        handler()
    except Exception as exc:
        # Clearing the guard matters: a failed reboot must not wedge the device
        # into refusing every later power action.
        print(f"Power action {action} failed: {exc}", flush=True)
        _clear_pending()


# --------------------------------------------------------------------- actions


def _do_reboot() -> None:
    print("Rebooting now", flush=True)
    _run_first_available((["systemctl", "reboot"], ["reboot"]))


def _do_shutdown() -> None:
    print("Shutting down now", flush=True)
    _run_first_available((["systemctl", "poweroff"], ["poweroff"]))


def _do_factory_reset() -> None:
    """Wipe the clock back to factory state, then reboot.

    Order is load-bearing. Deregistering needs the cloud token, so it has to
    happen before the config wipe removes it. Wi-Fi goes last of the wipes
    because losing the network early would guarantee the deregister fails.
    """
    print("Factory reset starting", flush=True)
    _deregister_from_cloud()
    _reset_runtime_config()
    wifi_ok = _forget_wifi()
    identity_ok = _forget_device_identity()

    problems = _verify_wiped()
    if not wifi_ok:
        problems.append("some saved Wi-Fi profiles could not be deleted")
    if not identity_ok:
        problems.append("the device id file could not be removed")

    if problems:
        # Deliberately do not reboot. Rebooting would hide the failure behind a
        # clock that looks freshly reset while still holding the customer's
        # credentials, and it would drop the network they need to retry over.
        print("FACTORY RESET INCOMPLETE - not rebooting:", flush=True)
        for problem in problems:
            print(f"  - {problem}", flush=True)
        raise RuntimeError("; ".join(problems))

    print("Factory reset complete, rebooting", flush=True)
    _do_reboot()


def _verify_wiped() -> list[str]:
    """Confirm the sensitive state is actually gone.

    Each wipe step swallows its own errors so that one failure does not abort
    the others, which means looking afterwards is the only honest way to say
    whether the device was reset. Cloud deregistration is excluded on purpose:
    it is remote, best effort, and its failure leaves an orphaned row rather
    than data on the device.
    """
    problems: list[str] = []

    if os.path.exists(os.environ.get("METROCLOCK_DEVICE_ID_PATH", DEVICE_ID_PATH)):
        problems.append("device id file is still present")

    remaining = config_manager.read_runtime_overrides()
    if str(remaining.get("METROCLOCK_CLOUD_DEVICE_TOKEN", "") or "").strip():
        problems.append("cloud device token is still in the config")

    try:
        with open(WPA_SUPPLICANT_PATH, "r", encoding="utf-8") as f:
            if _WPA_NETWORK_BLOCK.search(f.read()):
                problems.append("wpa_supplicant.conf still holds a saved network")
    except FileNotFoundError:
        pass
    except Exception as exc:
        problems.append(f"could not read wpa_supplicant.conf: {type(exc).__name__}")

    leftover = [name for name, _ in _saved_wifi_profiles()]
    if leftover:
        problems.append(f"{len(leftover)} Wi-Fi profile(s) still saved: {', '.join(leftover)}")

    return problems


def _saved_wifi_profiles() -> list[tuple[str, str]]:
    """Wireless NM profiles, excluding the clock's own setup hotspot."""
    if not shutil.which("nmcli"):
        return []
    hotspot_ssid = str(factory_defaults.FACTORY_DEFAULTS.get("WIFI_SETUP_HOTSPOT_SSID", "") or "")
    # --escape no, then split from the right: profile names may contain ':'
    # and terse output escapes it as '\:'. Splitting at every colon misreads
    # such a name, and the profile survives the reset with the customer's PSK
    # in it. core/wifi_setup.py takes the same care.
    listing = _run_capture(
        ["nmcli", "--escape", "no", "-t", "-f", "NAME,TYPE", "connection", "show"]
    )
    found = []
    for line in (listing or "").splitlines():
        name, separator, conn_type = line.rpartition(":")
        if not separator or "wireless" not in conn_type.lower():
            continue
        if name == hotspot_ssid:
            continue
        found.append((name, conn_type))
    return found


_ACTIONS: dict[str, Callable[[], None]] = {
    "reboot": _do_reboot,
    "shutdown": _do_shutdown,
    "factory_reset": _do_factory_reset,
}


def supported_actions() -> tuple[str, ...]:
    return tuple(sorted(_ACTIONS))


# ----------------------------------------------------------------- reset steps


def _deregister_from_cloud() -> None:
    """Ask the backend to forget this device. Best effort by design.

    An offline clock must still reset. The cost of failing here is an orphaned
    row the user can delete from the app, which is a far better outcome than a
    clock that cannot be reset without a network.
    """
    import requests  # local: keeps this path importable without requests

    base_url = str(getattr(config, "METROCLOCK_CLOUD_BASE_URL", "") or "").strip().rstrip("/")
    token = str(getattr(config, "METROCLOCK_CLOUD_DEVICE_TOKEN", "") or "").strip()
    if not base_url or not token:
        print("  no cloud pairing to deregister", flush=True)
        return

    import web_server  # local: avoids an import cycle at module load

    try:
        response = requests.post(
            f"{base_url}/api/devices/{web_server._get_device_id()}/deregister",
            headers={"Authorization": f"Bearer {token}"},
            timeout=DEREGISTER_TIMEOUT_SECONDS,
        )
        print(f"  deregister returned {response.status_code}", flush=True)
    except Exception as exc:
        print(f"  deregister failed, continuing anyway: {exc}", flush=True)


def _reset_runtime_config() -> None:
    previous = config_manager.read_runtime_overrides()
    # Provisioned keys, never the ones in the runtime config: a user may have
    # entered their own, and those must not survive into the next owner's hands.
    data = factory_defaults.build(provisioned=factory_defaults.load_provisioned())
    cleared = factory_defaults.cleared_keys(previous)
    config_manager.replace_config(data)
    print(f"  config reset, cleared {len(cleared)} personalised setting(s)", flush=True)


def _forget_wifi() -> bool:
    """Remove saved networks so the clock returns to the setup hotspot.

    Returns False if any deletion failed, so the caller can refuse to call the
    reset a success.
    """
    removed = 0
    failed = 0

    for name, _ in _saved_wifi_profiles():
        if _run(["nmcli", "connection", "delete", name]):
            removed += 1
        else:
            failed += 1
            print(f"  could not delete Wi-Fi profile: {name}", flush=True)

    if _clear_wpa_supplicant():
        removed += 1
    print(f"  removed {removed} saved network profile(s)", flush=True)
    return failed == 0


_WPA_NETWORK_BLOCK = re.compile(r"^\s*network\s*=\s*\{.*?^\s*\}\s*$", re.MULTILINE | re.DOTALL)


def _clear_wpa_supplicant() -> bool:
    """Strip saved networks but keep the header (country, ctrl_interface).

    Rewriting the file wholesale would drop the regulatory domain, and a Pi with
    no country set will not bring the 2.4GHz radio up at all.
    """
    try:
        with open(WPA_SUPPLICANT_PATH, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return False
    except Exception as exc:
        print(f"  could not read {WPA_SUPPLICANT_PATH}: {exc}", flush=True)
        return False

    stripped = _WPA_NETWORK_BLOCK.sub("", content).strip() + "\n"
    if stripped == content:
        return False

    try:
        with open(WPA_SUPPLICANT_PATH, "w", encoding="utf-8") as f:
            f.write(stripped)
        os.chmod(WPA_SUPPLICANT_PATH, 0o600)
        return True
    except Exception as exc:
        print(f"  could not rewrite {WPA_SUPPLICANT_PATH}: {exc}", flush=True)
        return False


def _forget_device_identity() -> bool:
    """Drop the device id so the clock comes back as a new unit."""
    path = os.environ.get("METROCLOCK_DEVICE_ID_PATH", DEVICE_ID_PATH)
    try:
        os.remove(path)
        print("  device id cleared, a new one is generated on boot", flush=True)
        return True
    except FileNotFoundError:
        return True
    except Exception as exc:
        print(f"  could not remove {path}: {type(exc).__name__}", flush=True)
        return False


# ------------------------------------------------------------------- utilities


def _run(args: list[str]) -> bool:
    try:
        subprocess.run(args, check=True, capture_output=True, timeout=20)
        return True
    except Exception:
        return False


def _run_capture(args: list[str]) -> str:
    try:
        result = subprocess.run(args, check=True, capture_output=True, timeout=20, text=True)
        return result.stdout or ""
    except Exception:
        return ""


def _run_first_available(candidates) -> None:
    for args in candidates:
        if shutil.which(args[0]) and _run(args):
            return
    raise RuntimeError(f"none of these commands succeeded: {candidates}")
