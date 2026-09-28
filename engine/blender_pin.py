"""The one Blender build the pipeline is graded against: 5.0.1 (decision made at the start of phase 6,
2026-09-28; plan `docs/superpowers/plans/2026-09-28-director-phase6-physics-sim.md`).

Stay on 5.0.1 for all of phase 6; do not install 5.2 into the pipeline. Every method phase 6 needs
(Bullet, legacy cloth, Mantaflow gas and liquid, the Geometry Nodes simulation zone and Bake node, the
volume-grid nodes, OpenVDB volumes, Alembic and PC2 caches) is already in 5.0.1. What 5.2 LTS adds for
physics (GN hair and cloth XPBD) is still experimental and matters for character garments and hair
(phase 8). An upgrade would reset graded work: the owner graded realism round 16 on 5.0.1, and a new
build changes noise, volume stepping and Principled defaults, so every golden render would be re-baked.
5.0 is not an LTS and gets no more fixes: if a 5.0.1 solver crash blocks a task, install 5.2 side by
side and point BLENDER_EXE at it for that one probe only, without switching the pipeline. The bake key
includes the Blender version, so an upgrade invalidates every cache automatically, and
`engine/tests/test_blender_pin.py` fails when the installed build drifts from PINNED_BLENDER, so a
change is always deliberate. Re-evaluate at the start of phase 8."""
import re

PINNED_BLENDER = "5.0.1"

_VERSION = re.compile(r"Blender (\d+\.\d+\.\d+)")


def parse_version(text):
    """'Blender 5.0.1\n\tbuild date: ...' -> '5.0.1'; None when the text names no version."""
    m = _VERSION.search(text or "")
    return m.group(1) if m else None
