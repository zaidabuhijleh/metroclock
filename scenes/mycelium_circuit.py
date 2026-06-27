from .abstract_core import render_mycelium_circuit_frame

NAME = "Mycelium Circuit"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_mycelium_circuit_frame(tick, FPS)
