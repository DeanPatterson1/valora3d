"""The preview's aerial haze reads a softened mist pass (Render Studio e2e 2026-09-28: 16 spp preview frames were
salt-and-peppered over the hazed trees; the denoised beauty without the haze was clean). Final is unchanged."""
import os
import subprocess
from pathlib import Path

import pytest

from engine.blender_cli import BLENDER
from engine.compiler.tiers import TIERS, mist_soften_px

REPO = Path(__file__).resolve().parents[2]


def test_only_the_cheap_tiers_soften_the_mist():
    assert mist_soften_px("final") == 0
    assert mist_soften_px("preview") == 5            # 540 px short side: the radius measured against 256 spp
    assert 1 <= mist_soften_px("keyframes") <= mist_soften_px("preview")
    assert set(TIERS) == {"keyframes", "preview", "final"}   # a new tier decides its own softening


_TREE = r'''
import sys
sys.path.insert(0, REPO)
import bpy
from engine.blender import grade
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.world = bpy.data.worlds.new("w")
scene.view_layers[0].use_pass_mist = True    # the Mist socket exists once the pass is on
scene[grade.HAZE_KEY] = {"color": [0.5, 0.5, 0.5], "halfM": 60.0, "max": 0.85}
out = {}
for tier in ("preview", "final", None):
    if tier is None:
        del scene["valora_tier"]
    else:
        scene["valora_tier"] = tier
    tree = bpy.data.node_groups.new("t", "CompositorNodeTree")
    N, L = tree.nodes, tree.links
    src = N.new("CompositorNodeRLayers")
    idm = N.new("CompositorNodeIDMask")
    grade._aerial(scene, N, L, src, src.outputs["Image"], idm.outputs["Alpha"])
    soft = N.get("haze_mist_soften")
    feeds = {l.to_node.name for l in src.outputs["Mist"].links}
    out[str(tier)] = (soft is not None and list(soft.inputs["Size"].default_value), sorted(feeds))
print("RESULT", out)
'''


@pytest.mark.blender
@pytest.mark.skipif(not os.path.exists(BLENDER), reason="Blender not installed")
def test_the_preview_grade_reads_the_softened_mist_and_final_the_raw_pass():
    code = f"REPO = {str(REPO)!r}\n" + _TREE
    p = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python-expr", code],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    line = next((ln for ln in p.stdout.splitlines() if ln.startswith("RESULT ")), None)
    assert p.returncode == 0 and line, p.stdout[-2000:] + p.stderr[-2000:]
    got = eval(line[len("RESULT "):])   # noqa: S307 - our own repr of plain lists
    assert got["preview"] == ([5.0, 5.0], ["haze_mist_soften"])            # the haze reads only the blur
    assert got["final"] == (False, ["haze_distance", "haze_sky_fade"])      # final: the raw pass, as before
    assert got["None"] == got["final"]
