from .abstract_core import render_phyllotaxis_bloom_frame

NAME = "Phyllotaxis Bloom"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_phyllotaxis_bloom_frame(tick, FPS)
