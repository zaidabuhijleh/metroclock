from . import (
    alpine_cabin,
    aurora_waves,
    beach,
    city_day,
    contour_drift,
    coral_reef,
    lava_lamp,
    liquid_chroma,
    lofi_cat,
    oil_slick,
    prism_weave,
    rainy_nook,
    ripple_tiles,
    sunset_trail,
    tea_by_candle,
    thermal_flow,
)

SCENES = [
    beach,
    city_day,
    sunset_trail,
    alpine_cabin,
    coral_reef,
    lofi_cat,
    rainy_nook,
    tea_by_candle,
    thermal_flow,
    liquid_chroma,
    oil_slick,
    lava_lamp,
    aurora_waves,
    contour_drift,
    prism_weave,
    ripple_tiles,
]

SCENE_KEYS = tuple(scene.__name__.split(".")[-1] for scene in SCENES)

COLLECTIONS = {
    collection: tuple(scene for scene in SCENES if scene.COLLECTION == collection)
    for collection in ("Places", "Cozy", "Flow", "Patterns")
}
