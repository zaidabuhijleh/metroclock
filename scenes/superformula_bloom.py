from .abstract_core import render_superformula_bloom_frame

NAME = "Superformula Bloom"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_superformula_bloom_frame(tick, FPS)
