"""Which lighting rigs a world pairs with (phase 5 Task 72). Pure.

A world manifest's `lightingPairs` lists the lighting blocks that belong in it, first = its default: the
studio keeps its softboxes and reflection rig; the outdoor worlds light from their own sky, sun, neon or street
lamps, plus reflection_rig for glossy subjects (TG-08 still picks it). A script whose lighting is not in its
world's pairs FAILS the check (lighting_world_mismatch, error). Until round 13 it was silently repaired to the
first pair: the r12 night street asked for the world's own light and got neon rims instead (owner's r12 review:
"an unknown/unsupported rig fails loudly instead of falling back"). The director only offers a world's pairs
(capabilities, fallback), so the error only ever meets a hand script or a model that ignored its brief.
A world without `lightingPairs` (test catalogs, future worlds) accepts any lighting."""
from engine.issues import Issue


def allowed_lighting(world_manifest):
    """The world's lighting pairs, or None when it names none (anything goes)."""
    pairs = (world_manifest or {}).get("lightingPairs")
    return list(pairs) if pairs else None


def check_lighting(s, catalog, issues):
    """An error when the script's lighting is not one its world pairs with; the script is never changed.
    Returns True when the lighting is refused."""
    world = catalog.get("world", (s.get("world") or {}).get("id")) or {}
    pairs = allowed_lighting(world)
    ref = s.get("lighting") or {}
    if not pairs or ref.get("id") in pairs:
        return False
    issues.append(Issue("lighting_world_mismatch", "lighting.id",
                        f"{ref.get('id')} does not light {world['id']}; it pairs with {', '.join(pairs)}", "error"))
    return True
