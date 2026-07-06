from PIL import Image, ImageDraw

import config_manager
import web_server
from widgets.clock import ClockWidget


class CustomWidget(ClockWidget):
    """Slot-based custom dashboard composition.

    The custom widget reuses the compact renderers from ClockWidget for now, but
    owns the clock_widget lifecycle and layout selection separately from the
    standalone clock mode.
    """

    def _effective_clock_size(self):
        return 0.5

    def update(self):
        config_manager.reload_config()

        if web_server.get_display_mode() != "clock_widget":
            return

        screen_layout = self._build_clock_screen_layout()
        sources_to_update = {pane.source for pane in screen_layout.widget_panes}

        for source in sources_to_update:
            presenter = self._widget_presenters.get(source)
            if presenter is None:
                continue
            presenter.update()

        self._rotate_embedded_indices()

    def draw(self):
        theme = self._clock_theme()
        self.canvas = Image.new("RGB", (self.width, self.height), theme.bg)
        draw = ImageDraw.Draw(self.canvas)

        screen_layout = self._build_clock_screen_layout()
        for pane in screen_layout.widget_panes:
            self._draw_widget_pane(draw, pane)

        return self.canvas
