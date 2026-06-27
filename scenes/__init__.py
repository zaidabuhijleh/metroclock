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
    caustic_lattice,
    crystal_mosaic,
    ember_bloom,
    endless_current,
    interference_bloom,
    kelp_current,
    lava_lamp,
    liquid_chroma,
    lofi_cat,
    mycelium_circuit,
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
    endless_current,
    biolume_bloom,
    caustic_lattice,
    coral_mist,
    oil_slick,
    lava_lamp,
    aurora_waves,
    contour_drift,
    ripple_tiles,
    sea_glass,
    ember_bloom,
    cellular_reef,
    crystal_mosaic,
    mycelium_circuit,
    interference_bloom,
]

SCENE_KEYS = tuple(scene.__name__.split(".")[-1] for scene in SCENES)

COLLECTIONS = {
    collection: tuple(scene for scene in SCENES if scene.COLLECTION == collection)
    for collection in ("Places", "Cozy", "Flow", "Patterns")
}
