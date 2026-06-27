from .abstract_core import render_ember_bloom_frame

NAME = "Ember Bloom"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_ember_bloom_frame(tick, FPS)
