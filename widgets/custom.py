import queue
import threading
import time

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_config_reload = 0.0
        self._update_queue = queue.Queue()
        self._queued_sources = set()
        self._last_source_update_request = {}
        self._queued_sources_lock = threading.Lock()
        self._update_worker = threading.Thread(target=self._run_update_worker, name="custom-widget-updates", daemon=True)
        self._update_worker.start()

    def _effective_clock_size(self):
        return 0.5

    def update(self):
        now = time.time()
        if now - self._last_config_reload >= 1.0:
            config_manager.reload_config()
            self._last_config_reload = now

        if web_server.get_display_mode() != "clock_widget":
            return

        screen_layout = self._build_clock_screen_layout()
        sources_to_update = {pane.source for pane in screen_layout.widget_panes}
        self._enqueue_source_updates(sources_to_update)
        self._rotate_embedded_indices()

    def _enqueue_source_updates(self, sources):
        now = time.time()
        for source in sources:
            source = str(source or "").strip().lower()
            if source == "clock" or source not in self._widget_presenters:
                continue
            with self._queued_sources_lock:
                if source in self._queued_sources:
                    continue
                if now - self._last_source_update_request.get(source, 0.0) < 1.0:
                    continue
                self._last_source_update_request[source] = now
                self._queued_sources.add(source)
            self._update_queue.put(source)

    def _run_update_worker(self):
        while True:
            source = self._update_queue.get()
            try:
                presenter = self._widget_presenters.get(source)
                if presenter is not None:
                    presenter.update()
            except Exception as exc:
                print(f"Custom widget source update failed ({source}): {exc}")
            finally:
                with self._queued_sources_lock:
                    self._queued_sources.discard(source)
                self._update_queue.task_done()

    def draw(self):
        theme = self._clock_theme()
        self.canvas = Image.new("RGB", (self.width, self.height), theme.bg)
        draw = ImageDraw.Draw(self.canvas)

        screen_layout = self._build_clock_screen_layout()
        for pane in screen_layout.widget_panes:
            self._draw_widget_pane(draw, pane)

        return self.canvas
