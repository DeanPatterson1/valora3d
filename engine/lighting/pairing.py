"""Which lighting rigs a world pairs with (phase 5 Task 72). Pure.

A world manifest's `lightingPairs` lists the lighting blocks that belong in it, first = its default: the
studio keeps its softboxes and reflection rig; the outdoor worlds light from their own sky, sun or neon,
plus reflection_rig for glossy subjects (TG-08 still picks it). A script whose lighting is not in its world's
pairs is repaired to the first pair, keeping the params the two blocks share by name
(lighting_world_mismatch, repaired): a studio softbox never ends up floating over a night street or
mirrored in a wet courtyard (chunk 3 look-check t68: the rim softbox's reflection in the wet ground).
A world without `lightingPairs` (test catalogs, future worlds) accepts any lighting."""
from engine.issues import Issue


def allowed_lighting(world_manifest):
    """The world's lighting pairs, or None when it names none (anything goes)."""
    pairs = (world_manifest or {}).get("lightingPairs")
    return list(pairs) if pairs else None


def repair_lighting(s, catalog, issues):
    """Swap a lighting block the world does not pair with for the world's first pair (params kept by name,
    the rest filled by the script repair). Returns True when it swapped."""
    from engine.script import _repair_params
    world = catalog.get("world", (s.get("world") or {}).get("id")) or {}
    pairs = allowed_lighting(world)
    ref = s.get("lighting") or {}
    if not pairs or ref.get("id") in pairs:
        return False
    new = catalog.get("lighting", pairs[0])
    old_params = ref.get("params") or {}
    kept = {k: v for k, v in old_params.items() if k in new["params"]}
    s["lighting"] = {"id": pairs[0], "params": kept}
    _repair_params(s["lighting"], new, "lighting", [])            # defaults for the rest, silently
    issues.append(Issue("lighting_world_mismatch", "lighting.id",
                        f"{ref.get('id')} does not light {world['id']}; used {pairs[0]}"
                        + (f" (kept {', '.join(sorted(kept))})" if kept else ""), "repaired"))
    return True
