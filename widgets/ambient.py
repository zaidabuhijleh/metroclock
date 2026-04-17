import time
from PIL import Image

import config
from core.widget import Widget
from scenes import SCENES


class AmbientWidget(Widget):
    def __init__(self, width, height):
        super().__init__(width, height)
        self._scene_index = 0
        self._frame_index = 0
        self._last_frame_time = time.time()
        self._scene_start_time = time.time()

    def _scene(self):
        return SCENES[self._scene_index % len(SCENES)]

    def update(self):
        now = time.time()
        scene = self._scene()

        if now - self._scene_start_time >= config.AMBIENT_SCENE_DURATION:
            self._scene_index = (self._scene_index + 1) % len(SCENES)
            self._frame_index = 0
            self._last_frame_time = now
            self._scene_start_time = now
            return

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
