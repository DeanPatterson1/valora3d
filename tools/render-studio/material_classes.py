"""Which calibration a snapshot material gets, decided from three signals.

The fleet carries three naming families: the browser's runtime `mv-*`
materials (the default Porsche), the parting engine's authored `MV_*`
materials (R34, Hellcat, S2000, ...) and raw artist names ("Headlight Glass",
"Window", "Tire") on cars that were never re-authored. Names alone cover the
first two; the third is only reachable through the slot tag the site writes on
every exported mesh (`mvSlot`), so a material is classified by name first and
by the slots that use it second. Pure, no bpy, unit-tested.
"""
from __future__ import annotations

LAMP_SLOTS = frozenset({
    'headlight-L', 'headlight-R', 'taillight-L', 'taillight-R', 'third-brake-light',
    'fog-light-L', 'fog-light-R', 'side-marker-L', 'side-marker-R', 'turn-signals',
    'drl-L', 'drl-R', 'reverse-light',
})
WINDOW_SLOTS = frozenset({'windshield', 'rear-window', 'side-windows', 'quarter-windows', 'sunroof', 'window-trim'})
TIRE_SLOTS = frozenset({'tire-FL', 'tire-FR', 'tire-RL', 'tire-RR'})

GLASSY_WORDS = ('glass', 'lens', 'cover', 'clear', 'transparent')


def classify(name, slots=(), alpha=1.0, transmission=0.0, metallic=0.0):
    """Return 'carbon' | 'paint' | 'privacy-glass' | 'lamp-lens' | 'rubber' | None.

    `slots` are the ModVision slot ids of the meshes that use the material.
    Name rules win; slot rules only claim what the name left unclassified and
    only with corroborating evidence (a glassy word or real transparency for a
    lens, a tire word or a tire-only material for rubber), so an opaque lamp
    housing or a rim never picks up glass or rubber.
    """
    lower = str(name or '').lower()
    base = lower.split('.')[0]
    if base.startswith('mv-carbon-weave'):
        return 'carbon'
    if base.startswith('mv-unified-paint'):
        return 'paint'
    if base.startswith('mv-window-tint') or base == 'mv_windowtint':
        return 'privacy-glass'
    if base.startswith('mv-smoke-lens') or base in ('mv_headlightglass', 'mv_tailglass'):
        return 'lamp-lens'
    if base == 'rubber' or base in ('mv_tirerubber', 'mv_wheeltire'):
        return 'rubber'

    slots = set(slots or ())
    if not slots:
        return None
    glassy = any(word in lower for word in GLASSY_WORDS)
    transparent = (alpha is not None and alpha < 0.999) or (transmission or 0) > 0.05
    if slots & LAMP_SLOTS and (glassy or transparent) and metallic < 0.5:
        return 'lamp-lens'
    if slots <= WINDOW_SLOTS and (glassy or transparent or 'window' in lower or 'tint' in lower):
        return 'privacy-glass'
    if slots <= TIRE_SLOTS and metallic < 0.5:          # a material only tires use is the tire
        return 'rubber'
    return None
