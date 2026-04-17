import time
from PIL import Image

import config
import web_server
from core.widget import Widget
from scenes import SCENES

_SCENE_KEYS = [s.__name__.split(".")[-1] for s in SCENES]


class AmbientWidget(Widget):
    def __init__(self, width, height):
        super().__init__(width, height)
        self._scene_index = 0
        self._frame_index = 0
        self._last_frame_time = time.time()
        self._scene_start_time = time.time()
        self._pinned_key = None

    def _resolve_scene_index(self):
        pinned = web_server.get_ambient_scene()
        if pinned and pinned in _SCENE_KEYS:
            idx = _SCENE_KEYS.index(pinned)
            if idx != self._pinned_key:
                # Scene was just pinned or changed — reset frame
                self._pinned_key = idx
                self._frame_index = 0
                self._last_frame_time = time.time()
            return idx
        self._pinned_key = None
        return self._scene_index % len(SCENES)

    def _scene(self):
        return SCENES[self._resolve_scene_index()]

    def update(self):
        now = time.time()
        pinned = web_server.get_ambient_scene()

        if not pinned:
            duration = getattr(config, "AMBIENT_SCENE_DURATION", 60)
            if now - self._scene_start_time >= duration:
                self._scene_index = (self._scene_index + 1) % len(SCENES)
                self._frame_index = 0
                self._last_frame_time = now
                self._scene_start_time = now
                return

        scene = self._scene()
        frame_interval = 1.0 / scene.FPS
        if now - self._last_frame_time >= frame_interval:
            self._frame_index = (self._frame_index + 1) % len(scene.FRAMES)
            self._last_frame_time = now

    def draw(self):
        scene = self._scene()
        frame = scene.FRAMES[self._frame_index % len(scene.FRAMES)]
        if frame.size == (self.width, self.height):
            self.canvas = frame.copy()
        else:
            self.canvas = frame.resize((self.width, self.height), Image.NEAREST)
        return self.canvas
