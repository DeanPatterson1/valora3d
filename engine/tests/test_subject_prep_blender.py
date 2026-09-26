"""Subject preparation inside Blender (realism pass 2026-09-25): fixture material setups on a synthetic car are
classified and calibrated, authored maps and unknown materials survive, and the node values read back as ported
from render-studio. Plus one compile of the sports_car fixture in the rain courtyard."""
import copy
import json
import subprocess
from pathlib import Path

import pytest

from engine.ingest.run import BLENDER
from engine.tests.conftest import requires_blender

pytestmark = [pytest.mark.blender, requires_blender]
ROOT = Path(__file__).resolve().parents[2]

_FIXTURE = r'''
import bpy, json, sys, math
from types import SimpleNamespace
sys.path.insert(0, {root!r})
bpy.ops.wm.read_factory_settings(use_empty=True)
from engine.blender.realism_rig import build_rig
root = bpy.data.objects.new("valora_subject", None); bpy.context.scene.collection.objects.link(root)
build_rig(bpy.context.scene, root)

def mat(name, blend=False, **kw):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    for k, v in kw.items():
        p.inputs[k].default_value = v
    return m

def obj(name, verts, faces, material):
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.update()
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o)
    o.parent = root; me.materials.append(material); return o

def ring(r0, r1, x0, x1, cy, cz, n=48):
    """A closed tube section: outer tread cylinder + two sidewall annuli (axle along X)."""
    v, f = [], []
    for x in (x0, x1):
        for r in (r0, r1):
            for i in range(n):
                t = 2 * math.pi * i / n
                v.append((x, cy + r * math.cos(t), cz + r * math.sin(t)))
    def idx(side, rad, i): return side * 2 * n + rad * n + (i % n)
    for i in range(n):
        f.append((idx(0, 1, i), idx(0, 1, i + 1), idx(1, 1, i + 1), idx(1, 1, i)))   # tread
        for s in (0, 1):
            f.append((idx(s, 0, i), idx(s, 0, i + 1), idx(s, 1, i + 1), idx(s, 1, i)))  # sidewalls
    return v, f

def box(lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    v = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return v, f

W = dict(center=[0.8, -1.2, 0.35], radius=0.35, axis=[1.0, 0.0, 0.0], width=0.26, tyreBand=[0.74, 1.0])
meshes = []
meshes.append(obj("tire-fl", *ring(0.26, 0.35, 0.68, 0.92, -1.2, 0.35),
                  mat("Rubber.001", **{{"Base Color": (.02, .02, .02, 1), "Roughness": .85}})))
meshes.append(obj("rotor-fl", *ring(0.07, 0.20, 0.79, 0.81, -1.2, 0.35),
                  mat("Brake Disc", **{{"Base Color": (.35, .32, .3, 1), "Metallic": .6, "Roughness": .5}})))
cap = mat("Manthey cap", **{{"Base Color": (.314, .195, .136, 1), "Metallic": 1.0, "Roughness": .55}})
cnt = cap.node_tree; cp = next(n for n in cnt.nodes if n.type == "BSDF_PRINCIPLED")
ctex = cnt.nodes.new("ShaderNodeTexImage"); ctex.image = bpy.data.images.new("cap_normal", 8, 8)
cnm = cnt.nodes.new("ShaderNodeNormalMap"); cnt.links.new(ctex.outputs["Color"], cnm.inputs["Color"])
cnt.links.new(cnm.outputs["Normal"], cp.inputs["Normal"])
meshes.append(obj("manthey-aero-disc-cap-l", *ring(0.02, 0.20, 0.905, 0.91, -1.2, 0.35), cap))
meshes.append(obj("caliper-front-l", *box((0.76, -1.28, 0.50), (0.84, -1.12, 0.56)),
                  mat("Brakes", **{{"Base Color": (.654, .481, 0, 1), "Metallic": .8, "Roughness": 1.0}})))
paint = mat("mv-body-paint", **{{"Base Color": (.85, .02, .02, 1), "Metallic": .7, "Roughness": .25}})
meshes.append(obj("door-l-shell", *box((-0.9, -1.0, 0.3), (0.9, 1.0, 1.1)), paint))
# authored maps: an image-textured, normal-mapped paint must keep both
img = bpy.data.images.new("upload_albedo", 8, 8)
mp = mat("Body Paint Mapped", **{{"Metallic": .0, "Roughness": .3}})
nt = mp.node_tree; p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img; nt.links.new(tex.outputs["Color"], p.inputs["Base Color"])
nm = nt.nodes.new("ShaderNodeNormalMap"); nt.links.new(tex.outputs["Color"], nm.inputs["Color"])
nt.links.new(nm.outputs["Normal"], p.inputs["Normal"])
meshes.append(obj("hood", *box((-0.6, -1.9, 0.9), (0.6, -1.1, 1.0)), mp))
carbon = mat("Carbon Fiber Glossy", **{{"Base Color": (.05, .05, .06, 1), "Metallic": .3, "Roughness": .15}})
meshes.append(obj("front-splitter-blade", *box((-0.7, -2.2, 0.1), (0.7, -2.0, 0.12)), carbon))
glass = mat("Glass", **{{"Base Color": (.03, .033, .038, 1), "Alpha": .42, "Roughness": .03}})
meshes.append(obj("windshield", *box((-0.6, -0.9, 0.9), (0.6, -0.4, 0.91)), glass))
meshes.append(obj("mirror-glass", *box((0.95, -0.7, 0.9), (0.96, -0.6, 0.95)), glass))
lens = mat("Headlight glass", **{{"Base Color": (.9, .93, .96, 1), "Alpha": .16, "Roughness": .04}})
meshes.append(obj("headlight-l-lens-9", *box((0.56, -2.0, 0.36), (0.82, -1.65, 0.6)), lens))
meshes.append(obj("headlight-l-lens-3", *box((0.66, -1.74, 0.52), (0.72, -1.72, 0.55)), lens))
drl = mat("Front DRL", **{{"Base Color": (1, 1, 1, 1), "Roughness": .1}})
meshes.append(obj("drl-l-ring-1", *box((0.66, -1.76, 0.47), (0.71, -1.75, 0.49)), drl))
tail = mat("Tail lights", **{{"Base Color": (.6, .05, .02, 1), "Roughness": .2}})
meshes.append(obj("taillight-l-tail-light-bar", *box((0.06, 1.65, 0.55), (0.72, 2.03, 0.58)), tail))
trim = mat("Matte Plastic", **{{"Base Color": (.03, .03, .03, 1), "Roughness": .75}})
meshes.append(obj("front-airduct-l", *box((0.3, -2.1, 0.2), (0.6, -2.0, 0.3)), trim))
unknown = mat("Material.004", **{{"Base Color": (.8, .8, .8, 1), "Roughness": .4}})
meshes.append(obj("Cube", *box((-0.2, 0.0, 1.1), (0.2, 0.4, 1.3)), unknown))
bpy.context.view_layer.update()

def digest(m):
    nt = m.node_tree
    return repr(sorted((n.bl_idname, tuple((i.identifier, repr(getattr(i, "default_value", None)) if not hasattr(
        getattr(i, "default_value", None), "__len__") else repr(tuple(i.default_value))) for i in n.inputs))
        for n in nt.nodes)) + repr(sorted((l.from_node.name, l.to_node.name, l.to_socket.identifier) for l in nt.links))
before = {{m.name: digest(m) for m in bpy.data.materials}}
prof = SimpleNamespace(wheels=[W], boundsMin=[-1.0, -2.3, 0.0], boundsMax=[1.0, 2.3, 1.4],
                       vehicle={{"forwardAxis": [0.0, 1.0, 0.0]}})
from engine.blender.subject_prep import prepare_subject
script = {{"world": {{"id": "rain_courtyard", "params": {{"wetness": 0.6}}}}, "effects": [{{"id": "rain", "params": {{}}}}]}}
rep = prepare_subject(meshes, script, prof, outdoor=True)

def up(sock, seen=None):
    seen = set() if seen is None else seen
    out = set()
    for l in sock.links:
        n = l.from_node
        if n.name in seen: continue
        seen.add(n.name); out.add(n.type)
        for i in n.inputs: out |= up(i, seen)
    return out

def principled(m):
    return next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")

def val(s):
    if s.is_linked: return "linked"
    v = s.default_value
    try: return [round(x, 4) for x in v]
    except TypeError: return round(v, 4)

res = {{"report": rep, "lettering": sorted(o.parent.name for o in bpy.data.objects if o.name.startswith("valora_prep_lettering")),
       "unknownSame": digest(unknown) == before["Material.004"], "mats": {{}}}}
for o in meshes:
    for m in o.data.materials:
        p = principled(m); out = next(n for n in m.node_tree.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
        res["mats"][o.name] = {{"material": m.name, "role": m.get("valora_prep"),
            "surface": out.inputs["Surface"].links[0].from_node.type if out.inputs["Surface"].is_linked else None,
            **{{k: val(p.inputs[k]) for k in ("Metallic", "Roughness", "Coat Weight", "Coat Roughness", "Coat IOR",
               "Specular IOR Level", "Emission Strength", "Emission Color", "Alpha", "Transmission Weight", "IOR",
               "Base Color")}},
            "baseUp": sorted(up(p.inputs["Base Color"])), "normalUp": sorted(up(p.inputs["Normal"])),
            "coatNormalUp": sorted(up(p.inputs["Coat Normal"])), "roughUp": sorted(up(p.inputs["Roughness"])),
            "values": [round(n.outputs[0].default_value, 4) for n in m.node_tree.nodes if n.type == "VALUE"],
            "rgb": [[round(x, 4) for x in n.outputs[0].default_value] for n in m.node_tree.nodes if n.type == "RGB"],
            "attrs": sorted(a.name for a in o.data.attributes if a.name.startswith("valora_prep"))}}
print("PREP-JSON" + json.dumps(res))
'''


@pytest.fixture(scope="module")
def prepped(tmp_path_factory):
    d = tmp_path_factory.mktemp("prep")
    script = d / "prep.py"
    script.write_text(_FIXTURE.format(root=str(ROOT)), encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                           "--python", str(script)], capture_output=True, text=True, timeout=300)
    line = next((l for l in proc.stdout.splitlines() if l.startswith("PREP-JSON")), None)
    assert proc.returncode == 0 and line, proc.stdout[-3000:] + proc.stderr[-3000:]
    return json.loads(line[len("PREP-JSON"):])


def test_every_fixture_role_is_found(prepped):
    roles = {o: m["role"] for o, m in prepped["mats"].items()}
    assert roles == {
        "tire-fl": "tyre", "rotor-fl": "rotor", "manthey-aero-disc-cap-l": "aero-disc", "caliper-front-l": "caliper", "door-l-shell": "paint",
        "hood": "paint", "front-splitter-blade": "carbon", "windshield": "window-glass", "mirror-glass": "mirror",
        "headlight-l-lens-9": "lamp-cover", "headlight-l-lens-3": "lamp-optic", "drl-l-ring-1": "lamp-drl",
        "taillight-l-tail-light-bar": "lamp-tail", "front-airduct-l": "trim-matte", "Cube": None}


def test_an_unrecognised_material_is_untouched(prepped):
    assert prepped["unknownSame"] is True


def test_paint_is_calibrated_not_replaced(prepped):
    p = prepped["mats"]["door-l-shell"]
    assert p["Coat Weight"] == 1.0 and p["Coat IOR"] == 1.5 and p["IOR"] == 1.5
    assert p["Coat Roughness"] == "linked" and "TEX_NOISE" in p["coatNormalUp"]      # lacquer peel
    assert [0.85, 0.02, 0.02, 1.0] in p["rgb"] and "GROUP" in p["baseUp"]   # the upload's pigment, under road film
    assert "TEX_VORONOI" in p["normalUp"]                        # metallic .7: flakes under the lacquer
    m = prepped["mats"]["hood"]
    assert "TEX_IMAGE" in m["baseUp"] and "NORMAL_MAP" in m["normalUp"]   # authored maps survive
    assert m["Specular IOR Level"] == 0.15                       # a solid pigment under lacquer


def test_glass_becomes_a_thin_sheet_and_the_mirror_silvered(prepped):
    g = prepped["mats"]["windshield"]
    assert g["surface"] == "MIX_SHADER"
    m = prepped["mats"]["mirror-glass"]
    assert m["material"] != prepped["mats"]["windshield"]["material"]
    assert m["Metallic"] == 1.0 and m["Alpha"] == 1.0 and m["Roughness"] <= 0.03


def test_lamp_cover_and_internal_optic_are_separated(prepped):
    cover, optic = prepped["mats"]["headlight-l-lens-9"], prepped["mats"]["headlight-l-lens-3"]
    assert cover["material"] != optic["material"]
    for m in (cover, optic):
        assert m["surface"] == "MIX_SHADER" and m["Alpha"] == 1.0 and m["Transmission Weight"] == 1.0
    assert optic["Base Color"][:3] == [0.98, 0.98, 0.98] and cover["Coat Weight"] == 0.0


def test_lamps_are_led_bright_in_an_outdoor_scene(prepped):
    drl, tail = prepped["mats"]["drl-l-ring-1"], prepped["mats"]["taillight-l-tail-light-bar"]
    assert drl["Emission Strength"] == 240.0 and drl["Emission Color"][:3] == [0.8, 0.89, 1.0]
    assert tail["Emission Strength"] == 95.0 and tail["Emission Color"][:3] == [1.0, 0.03, 0.012]


def test_tyre_rotor_caliper_trim_carbon_values(prepped):
    t = prepped["mats"]["tire-fl"]
    assert t["Roughness"] == "linked" and "TEX_NOISE" in t["normalUp"] and "ATTRIBUTE" in t["normalUp"]
    assert "valora_prep_wheel" in t["attrs"] and t["Coat IOR"] == 1.333      # wet sheen near the ground
    r = prepped["mats"]["rotor-fl"]
    # the fixture's dark authored disc (lum .32) is carbon-ceramic: nearly dielectric (critique mat-v2 #4)
    assert r["Metallic"] == 0.1 and r["Coat Weight"] == 0.0 and "ATTRIBUTE" in r["roughUp"]
    a = prepped["mats"]["manthey-aero-disc-cap-l"]
    # round 7: the copper aero-disc cap wears the front discs' carbon-ceramic look, its normal map kept
    assert a["Metallic"] == 0.1 and a["Coat Weight"] == 0.0 and a["Base Color"] == "linked"
    assert "NORMAL_MAP" in a["normalUp"] and "ATTRIBUTE" in a["roughUp"] and a["Specular IOR Level"] == 0.5
    assert [0.2, 0.2, 0.2, 1.0] in a["rgb"]               # a dark neutral grey under the ceramic chain, not copper
    c = prepped["mats"]["caliper-front-l"]
    assert (c["Metallic"], c["Coat Weight"], c["Specular IOR Level"]) == (0.0, 1.0, 0.2)
    assert c["Base Color"][:3] == [0.654, 0.481, 0.0]
    tr = prepped["mats"]["front-airduct-l"]
    assert tr["Roughness"] == "linked" or tr["Roughness"] == 0.50        # matte aero .4-.55 (mat-v2 #4)
    assert "TEX_NOISE" in tr["normalUp"] and "BEVEL" in tr["normalUp"]
    cf = prepped["mats"]["front-splitter-blade"]
    assert (cf["Metallic"], cf["Specular IOR Level"], cf["Coat Weight"]) == (0.0, 0.2, 1.0)
    assert cf["Coat Roughness"] == "linked" and 0.13 in cf["values"]          # wet resin .13 (mat-v2 #4), under the film
    assert set(cf["coatNormalUp"]) <= {"BEVEL"} and "TEX_CHECKER" in cf["baseUp"]   # smooth resin (bevelled edges)


def test_a_static_cars_tyre_gets_moulded_sidewall_lettering(prepped):
    assert prepped["report"]["letterFaces"] > 100 and prepped["lettering"] == ["tire-fl"]


def test_road_film_reaches_the_exterior_paint_and_is_reported(prepped):
    rep = prepped["report"]
    assert rep["conditions"]["wet"] and rep["roadFilm"] and "mv-body-paint" in rep["roadFilm"]
    assert "GROUP" in prepped["mats"]["door-l-shell"]["baseUp"]


def test_the_sports_car_compiles_with_its_materials_prepared(tmp_path):
    from engine.compiler.run import compile_scene
    from engine.tests.test_blocks_phase5_blender import T3, _glb
    from engine.tests.test_director_package import _p
    glb = _glb("sports_car")
    s = copy.deepcopy(T3)
    s["world"] = {"id": "rain_courtyard", "params": {"wetness": 0.6, "timeOfDay": "overcast_day", "dressing": "sparse"}}
    res = compile_scene(s, _p("sports_car"), glb, tmp_path, render=False, skip_kinds=("grade",))
    roles = {m["material"]: m["role"] for m in res["subjectPrep"]["materials"]}
    for name, role in {"mv-body-paint": "paint", "Carbon Fiber Glossy": "carbon", "Glass": "window-glass",
                       "Front DRL": "lamp-drl", "Tail lights": "lamp-tail", "Rubber.001": "tyre",
                       "Brake Disc": "rotor", "Brakes": "caliper", "Rims": "rim",
                       "Matte Plastic": "trim-matte"}.items():
        assert roles.get(name) == role, (name, roles.get(name))
    assert "Aluminum" not in roles and "Leather Black" not in roles
    assert res["uploadMaterials"]["before"] == res["uploadMaterials"]["after"]    # blocks still never edit them
