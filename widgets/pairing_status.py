from core.widget import Widget
from widgets.device_message import DeviceMessageScreen


class PairingStatusWidget(Widget):
    def __init__(self, width, height):
        super().__init__(width, height)
        self._screen = DeviceMessageScreen(width, height)

    def update(self):
        pass

    def draw(self):
        self.canvas = self._screen.render(("CONNECT TO", "DEVICE VIA", "APP"))
        return self.canvas
