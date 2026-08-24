from core.widget import Widget
from widgets.device_message import DeviceMessageScreen


class SetupStatusWidget(Widget):
    def __init__(self, width, height, status_provider):
        super().__init__(width, height)
        self._status_provider = status_provider
        self._screen = DeviceMessageScreen(width, height)

    def update(self):
        pass

    def draw(self):
        status = self._status_provider() or {}
        reason = str(status.get("reason") or "WiFi setup")
        last_error = str(status.get("last_error") or "")
        if self._is_network_error(reason, last_error):
            self.canvas = self._screen.render(("NETWORK", "ERROR", "OPEN APP"))
        else:
            self.canvas = self._screen.render(("CONNECT TO", "DEVICE VIA", "APP"))
        return self.canvas

    @staticmethod
    def _is_network_error(reason, last_error):
        text = f"{reason} {last_error}".upper()
        return any(
            marker in text
            for marker in (
                "BLOCKED",
                "COULD NOT",
                "ERROR",
                "FAIL",
                "LOST",
                "MISSING",
                "RFKILL",
            )
        )
