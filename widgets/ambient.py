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
        self._pinned_index = None
        # draw() runs every render tick, but update() only advances the frame
        # index at the scene's own FPS. render_frame is a pure function of the
        # tick, so re-rendering an unchanged index produces identical pixels —
        # cache the last one instead of recomputing it several times per frame.
        self._cache_key = None
        self._cache_frame = None

    def _resolve_scene_index(self):
        pinned = web_server.get_ambient_scene()
        if pinned and pinned in _SCENE_KEYS:
            idx = _SCENE_KEYS.index(pinned)
            if idx != self._pinned_index:
                # Scene was just pinned or changed — reset frame
                self._pinned_index = idx
                self._frame_index = 0
                self._last_frame_time = time.time()
            return idx
        self._pinned_index = None
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
            if hasattr(scene, "render_frame"):
                self._frame_index += 1
            else:
                self._frame_index = (self._frame_index + 1) % len(scene.FRAMES)
            self._last_frame_time = now

    def draw(self):
        scene = self._scene()
        # Scene identity is part of the key so rotation and app-pinned scene
        # changes invalidate the cache, not just a moving frame index.
        cache_key = (scene.__name__, self._frame_index)
        if cache_key != self._cache_key:
            self._cache_frame = self._render_scene_frame(scene)
            self._cache_key = cache_key
        # Hand out a copy: the cached image is reused across ticks and must not
        # be mutated by whatever consumes the frame.
        self.canvas = self._cache_frame.copy()
        return self.canvas

    def _render_scene_frame(self, scene):
        if hasattr(scene, "render_frame"):
            frame = scene.render_frame(self._frame_index)
        else:
            frame = scene.FRAMES[self._frame_index % len(scene.FRAMES)]
        if frame.size != (self.width, self.height):
            frame = frame.resize((self.width, self.height), Image.NEAREST)
        return frame
