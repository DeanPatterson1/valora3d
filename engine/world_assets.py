"""Which photographic assets each world needs, and the final-tier rule (realism audit #13).

A world's procedural fallbacks (noise asphalt, procedural grass, a physical sky, no trees) keep previews and tests
building with an empty library, but a paid final must never silently ship them. compile_scene calls
check_final_assets() before Blender starts: at the final tier every asset the chosen world (and time of day) needs
must resolve (pinned, hash-clean), else AssetMissing names them; at any other tier the missing ids are returned
and reported as the run's `assetFallbacks`. Pure: resolves through engine.assets, never imports bpy."""
from engine.assets import AssetError, resolve, resolve_gltf

FINAL = "final"
ASPHALT = tuple(f"asphalt_02_{k}" for k in ("diff", "rough", "nor_gl", "disp"))
PAVEMENT = tuple(f"concrete_pavement_{k}_2k" for k in ("diff", "rough", "nor_gl"))
COURTYARD_HDRI = {"final": "cloudy_vondelpark_8k", "other": "cloudy_vondelpark_4k"}   # render-studio: 8k first
STREET_HDRI = {"night": "cobblestone_street_night_4k", "dusk": "neuer_zollhof_4k",
               "twilight": "urban_street_01_4k", "overcast_day": "urban_street_01_4k"}


class AssetMissing(AssetError):
    pass


def courtyard_hdri(tier):
    """The courtyard sky for a tier: the 8k panorama at final (a telephoto crop or a smooth paint reflection
    magnifies a 4k one ~6.6x, rain_scene.py:11-20), the 4k one for previews."""
    return COURTYARD_HDRI["final" if tier == FINAL else "other"]


def _field_hdri(tod):
    from engine.blocks.world.golden_field.build import HDRI
    return HDRI[tod][0] if tod in HDRI else None


def required(world_id, params, tier):
    """(files, gltfs): the pinned ids this world needs for its photographic build at this tier."""
    tod = (params or {}).get("timeOfDay")
    if world_id == "rain_courtyard":
        return (courtyard_hdri(tier), *ASPHALT), ("grass_medium_01_1k", "tree_small_02_1k")
    if world_id == "night_street":
        return ((STREET_HDRI.get(tod, STREET_HDRI["night"]), *ASPHALT, *PAVEMENT),
                ("modular_urban_apartments_facade_1k", "street_lamp_01_1k"))
    if world_id == "golden_field":
        files = [h for h in (_field_hdri(tod),) if h]
        files += [f"{s}_{k}_2k" for s in ("withered_grass", "leafy_grass") for k in ("diff", "rough", "nor_gl")]
        return tuple(files), ("grass_medium_02_1k", "grass_medium_01_1k", "tree_small_02_1k")
    return (), ()


def missing(world_id, params, tier, root=None, manifest=None):
    files, gltfs = required(world_id, params, tier)
    out = [a for a in files if resolve(a, root, manifest) is None]
    return out + [a for a in gltfs if resolve_gltf(a, root, manifest) is None]


def check_final_assets(script, tier, root=None, manifest=None):
    """[] when nothing is missing; the missing ids at a non-final tier (the run reports its fallbacks);
    AssetMissing at the final tier."""
    w = script.get("world") or {}
    gone = missing(w.get("id"), w.get("params"), tier, root, manifest)
    if gone and tier == FINAL:
        raise AssetMissing(f"final render of {w.get('id')} needs its photographic assets; missing or unpinned: "
                           f"{', '.join(gone)} (procedural fallbacks are for previews and tests only)")
    return gone
