from .abstract_core import render_interference_bloom_frame

NAME = "Interference Bloom"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_interference_bloom_frame(tick, FPS)
