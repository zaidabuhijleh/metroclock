from .abstract_core import render_lace_diffusion_frame

NAME = "Lace Diffusion"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_lace_diffusion_frame(tick, FPS)
