from . import (
    alpine_cabin,
    aurora_waves,
    beach,
    city_day,
    contour_drift,
    coral_mist,
    coral_reef,
    ember_bloom,
    kelp_current,
    lava_lamp,
    liquid_chroma,
    lofi_cat,
    oil_slick,
    ripple_tiles,
    sea_glass,
    sunset_trail,
    thermal_flow,
)

SCENES = [
    beach,
    city_day,
    sunset_trail,
    alpine_cabin,
    coral_reef,
    lofi_cat,
    thermal_flow,
    liquid_chroma,
    kelp_current,
    coral_mist,
    oil_slick,
    lava_lamp,
    aurora_waves,
    contour_drift,
    ripple_tiles,
    sea_glass,
    ember_bloom,
]

SCENE_KEYS = tuple(scene.__name__.split(".")[-1] for scene in SCENES)

COLLECTIONS = {
    collection: tuple(scene for scene in SCENES if scene.COLLECTION == collection)
    for collection in ("Places", "Cozy", "Flow", "Patterns")
}
