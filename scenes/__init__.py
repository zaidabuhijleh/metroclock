from . import (
    alpine_cabin,
    aurora_waves,
    beach,
    biolume_bloom,
    cellular_reef,
    city_day,
    contour_drift,
    coral_mist,
    coral_reef,
    ember_bloom,
    endless_current,
    kelp_current,
    lava_lamp,
    liquid_chroma,
    lofi_cat,
    neon_ribbons,
    oil_slick,
    ripple_tiles,
    sea_glass,
    sunset_trail,
    thermal_flow,
    vector_plankton,
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
    endless_current,
    biolume_bloom,
    vector_plankton,
    coral_mist,
    oil_slick,
    lava_lamp,
    aurora_waves,
    contour_drift,
    ripple_tiles,
    sea_glass,
    ember_bloom,
    cellular_reef,
    neon_ribbons,
]

SCENE_KEYS = tuple(scene.__name__.split(".")[-1] for scene in SCENES)

COLLECTIONS = {
    collection: tuple(scene for scene in SCENES if scene.COLLECTION == collection)
    for collection in ("Places", "Cozy", "Flow", "Patterns")
}
