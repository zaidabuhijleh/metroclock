from .abstract_core import render_automata_glow_frame

NAME = "Automata Glow"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_automata_glow_frame(tick, FPS)
