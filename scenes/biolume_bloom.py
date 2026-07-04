from .abstract_core import render_biolume_bloom_frame

NAME = "Biolume Bloom"
COLLECTION = "Flow"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_biolume_bloom_frame(tick, FPS)
