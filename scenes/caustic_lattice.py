from .abstract_core import render_caustic_lattice_frame

NAME = "Caustic Lattice"
COLLECTION = "Flow"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_caustic_lattice_frame(tick, FPS)
