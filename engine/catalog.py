"""Block catalog: every world/lighting/camera/motion/effect/grade the director may use.

The rulebook's menu is generated from these manifests (phase 3), so what the AI reads and
what the code builds cannot drift apart.
"""
import copy
import importlib.util
import json
import re
import sys
from pathlib import Path

# realism / field / sim: research/physics/BLOCKS.md §1 (realism = always-on defaults the director never
# chooses; field = the one wind; sim = baked, subject-interacting simulations). Folders may be absent.
KINDS = ("world", "lighting", "camera", "motion", "effect", "grade", "edit", "realism", "field", "sim")
TIERS = ("T1", "T2", "T3", "T4")
ASPECTS = ("9:16", "16:9", "1:1", "4:5")
BLOCKS_DIR = Path(__file__).parent / "blocks"
_REQUIRED = ("id", "kind", "description", "params", "subjectSizeM", "aspects", "costWeight", "tags",
             "tierMax")
_CAMERA_PARAMS = ("distance", "lensMm", "fstop")
# CameraBench move names: the starter blocks' own values (arc, dolly) plus the standard set.
CAMERA_MOVES = ("static", "pan", "tilt", "dolly_in", "dolly_out", "truck", "pedestal", "arc",
                "orbit", "crane", "zoom_in", "zoom_out", "roll", "track", "push_in", "pull_out",
                "dolly")


_CAP = re.compile(r"^[a-z_]+\.[a-z_]+$")
REQUIRES_PROFILE = ("animationClips", "wheels", "parts", "rigged", "softParts", "danglingParts",
                    "rollAxis", "supportPolygon", "upFacing")      # the last three: engine/physics/shape.py


class CatalogError(ValueError):
    pass


# Physics (research/physics/BLOCKS.md §1-§2). Ground types drive realism appliesWhen and auto params.
GROUND_TYPES = ("studio", "asphalt", "dirt", "gravel", "sand", "snow", "grass", "water", "interior_floor", "rug")
MOTION_FLAGS = ("translates", "stops", "lands", "playsClip")   # what a motion block does to the subject
                                                               # (playsClip: the model's own clip deforms it)
PROFILE_FACTS = ("wheels", "wheelsSeparable", "tyreBand", "bodySeparable", "softParts", "softGround",
                 "danglingParts", "rigged", "rollAxis", "supportPolygon", "upFacing")  # engine/physics/applies.py computes each
MATERIAL_CLASSES = ("emissive", "glass", "skin", "metal", "glossy", "fabric", "matte")  # measure.material_class
_APPLIES_KEYS = ("placement", "profile", "profileNot", "world", "motion", "motionNot", "effects", "materials",
                 "sizeM")
# Phase 5 (Task 54): world weather/tone/lane keys, effect couplings, camera follow mode.
WEATHERS = ("dry", "wet", "rain", "snow", "fog")          # dice.json weather values (phase 4)
TEMPERATURES = ("cold", "mild", "hot")
FOLLOWS = ("anchor", "subject")
WORLD_REQ_KEYS = {"outdoor": bool, "hasGround": bool, "hasFoliage": bool, "groundType": list, "temperature": list}
_WIND_PARAM = re.compile(r"^(?:wind(?!ows?(?:[A-Z_]|$))|gust)", re.I)   # windowsLit is not wind
_TAXON = re.compile(r"^[A-Z]{2}-\d{2}$")


_TAG_KEYS = ("mood", "energy", "palette")


def _is_num(v):
    """True for int/float but not bool (bool is an int subclass)."""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check_types(where, m):
    if not isinstance(m["params"], dict):
        raise CatalogError(f"{where}: params must be an object")
    for name, spec in m["params"].items():
        if not isinstance(spec, dict):
            raise CatalogError(f"{where}: param '{name}' spec must be an object")
    size = m["subjectSizeM"]
    if not (isinstance(size, list) and len(size) == 2 and all(_is_num(v) for v in size)):
        raise CatalogError(f"{where}: subjectSizeM must be a list of 2 numbers")
    if not isinstance(m["aspects"], list):
        raise CatalogError(f"{where}: aspects must be a list")
    cw = m["costWeight"]
    if not _is_num(cw) or cw <= 0:
        raise CatalogError(f"{where}: costWeight must be a number > 0")
    tags = m["tags"]
    if not isinstance(tags, dict) or set(tags) != set(_TAG_KEYS):
        raise CatalogError(f"{where}: tags must have exactly the keys {list(_TAG_KEYS)}")
    for k in _TAG_KEYS:
        v = tags[k]
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            raise CatalogError(f"{where}: tags.{k} must be a list of strings")
    if m["tierMax"] not in TIERS:
        raise CatalogError(f"{where}: tierMax must be one of {list(TIERS)}")


def clamp_number(spec, v):
    """A number param's value inside its spec: [min, max], and with `zeroOrMin` either exactly 0 (the sentinel,
    e.g. rain's "from the intensity preset") or at least zeroOrMin. A tiny positive value such as 1e-200 passes
    [min, max] but breaks physical maths (review chunk3 #1), so it lifts to zeroOrMin."""
    v = float(min(max(v, spec["min"]), spec["max"]))
    z = spec.get("zeroOrMin")
    if z is not None and 0 < v < z:
        v = float(z)
    return v


def _check_param(where, name, spec):
    t = spec.get("type")
    if t == "number":
        lo, hi, d = spec.get("min"), spec.get("max"), spec.get("default")
        if not all(_is_num(v) for v in (lo, hi, d)):
            raise CatalogError(f"{where}: param '{name}' needs numeric min/max/default")
        if lo > hi:
            raise CatalogError(f"{where}: param '{name}' min > max")
        if not lo <= d <= hi:
            raise CatalogError(f"{where}: param '{name}' default outside [{lo}, {hi}]")
        if "zeroOrMin" in spec:
            z = spec["zeroOrMin"]
            if not (_is_num(z) and lo == 0 and 0 < z <= hi and (d == 0 or d >= z)):
                raise CatalogError(f"{where}: param '{name}' zeroOrMin needs min 0, 0 < zeroOrMin <= max and "
                                   "a default of 0 or >= zeroOrMin")
    elif t == "enum":
        vals = spec.get("values")
        if not vals or spec.get("default") not in vals:
            raise CatalogError(f"{where}: param '{name}' enum needs values containing default")
    elif t == "bool":
        if not isinstance(spec.get("default"), bool):
            raise CatalogError(f"{where}: param '{name}' bool needs a bool default")
    else:
        raise CatalogError(f"{where}: param '{name}' has unknown type {t!r}")


def _str_list(where, aw, key, allowed=None):
    v = aw.get(key, [])
    if (not isinstance(v, list) or not all(isinstance(x, str) for x in v)
            or (allowed is not None and set(v) - set(allowed))):
        raise CatalogError(f"{where}: appliesWhen.{key} must be a list of strings"
                           + (f" from {list(allowed)}" if allowed is not None else ""))


def _check_applies(where, aw):
    """appliesWhen: every present key must hold (AND). Resolved by engine/physics/applies.py."""
    if not isinstance(aw, dict) or set(aw) - set(_APPLIES_KEYS):
        raise CatalogError(f"{where}: appliesWhen must be an object with keys from {list(_APPLIES_KEYS)}")
    _str_list(where, aw, "placement", ("ground", "float"))
    _str_list(where, aw, "profile", PROFILE_FACTS)
    _str_list(where, aw, "profileNot", PROFILE_FACTS)
    _str_list(where, aw, "motion", MOTION_FLAGS)
    _str_list(where, aw, "motionNot", MOTION_FLAGS)
    _str_list(where, aw, "effects")
    w = aw.get("world", {})
    if (not isinstance(w, dict) or set(w) - {"groundType", "hasFoliage"}
            or ("groundType" in w and (not isinstance(w["groundType"], list) or set(w["groundType"]) - set(GROUND_TYPES)))
            or ("hasFoliage" in w and not isinstance(w["hasFoliage"], bool))):
        raise CatalogError(f"{where}: appliesWhen.world takes groundType (list from {list(GROUND_TYPES)}) "
                           "and hasFoliage (bool)")
    mats = aw.get("materials", {})
    if (not isinstance(mats, dict) or set(mats) - set(MATERIAL_CLASSES)
            or not all(_is_num(v) and 0 < v <= 1 for v in mats.values())):
        raise CatalogError(f"{where}: appliesWhen.materials maps a material class to a share in (0, 1]")
    if "sizeM" in aw:
        s = aw["sizeM"]
        if not (isinstance(s, list) and len(s) == 2 and all(_is_num(v) for v in s) and 0 <= s[0] <= s[1]):
            raise CatalogError(f"{where}: appliesWhen.sizeM must be [min, max] metres")


def _check_physics_meta(where, p):
    if not isinstance(p, dict):
        raise CatalogError(f"{where}: physics must be an object")
    tx = p.get("taxonomy", [])
    if not isinstance(tx, list) or not all(isinstance(t, str) and _TAXON.match(t) for t in tx):
        raise CatalogError(f"{where}: physics.taxonomy must be TAXONOMY ids like 'CD-02'")
    if p.get("state", "stateless") not in ("stateless", "baked"):
        raise CatalogError(f"{where}: physics.state must be 'stateless' or 'baked'")
    for k in ("touchesSubject", "windDriven"):
        if not isinstance(p.get(k, False), bool):
            raise CatalogError(f"{where}: physics.{k} must be true or false")
    for k in ("couplings", "excludes"):
        v = p.get(k, [])
        if not isinstance(v, list) or not all(isinstance(x, str) and x for x in v):
            raise CatalogError(f"{where}: physics.{k} must be a list of block ids")
    rw = p.get("requiresWorld", {})
    if not isinstance(rw, dict) or set(rw) - set(WORLD_REQ_KEYS):
        raise CatalogError(f"{where}: physics.requiresWorld keys are {sorted(WORLD_REQ_KEYS)}")
    for k, typ in WORLD_REQ_KEYS.items():
        if k in rw and not isinstance(rw[k], typ):
            raise CatalogError(f"{where}: physics.requiresWorld.{k} must be {typ.__name__}")
    tsp = p.get("timeScaleParam")
    if tsp is not None and not isinstance(tsp, str):
        raise CatalogError(f"{where}: physics.timeScaleParam names a param or is null")
    wc = p.get("windCalibration")
    if wc is not None and not (isinstance(wc, dict) and isinstance(wc.get("unit"), str) and _is_num(wc.get("perMs"))):
        raise CatalogError(f"{where}: physics.windCalibration is {{unit, perMs}}")


def _check_world_phase5(where, m):
    if not isinstance(m.get("outdoor", False), bool):
        raise CatalogError(f"{where}: outdoor must be true or false")
    ws = m.get("weathers", ["dry"])
    if not isinstance(ws, list) or not ws or "dry" not in ws or set(ws) - set(WEATHERS):
        raise CatalogError(f"{where}: weathers must list values of {list(WEATHERS)} including 'dry'")
    if m.get("temperature", "mild") not in TEMPERATURES:
        raise CatalogError(f"{where}: temperature must be one of {list(TEMPERATURES)}")
    tod = m.get("timeOfDay")
    if tod is not None:
        spec = m["params"].get(tod.get("param")) if isinstance(tod, dict) else None
        vals = tod.get("values") if isinstance(tod, dict) else None
        if (not spec or spec.get("type") != "enum" or not isinstance(vals, list) or not vals
                or set(vals) - set(spec.get("values", []))):
            raise CatalogError(f"{where}: timeOfDay names an enum param and a subset of its values")
    tp = m.get("toneParam")
    if tp is not None and tp not in m["params"]:
        raise CatalogError(f"{where}: toneParam must name one of its params or be null")
    lp = m.get("lightingPairs")
    if lp is not None and (not isinstance(lp, list) or not lp or not all(isinstance(x, str) for x in lp)):
        raise CatalogError(f"{where}: lightingPairs must be a non-empty list of lighting ids")
    lane = m.get("driveLaneM", 0.0)
    if not _is_num(lane) or lane < 0:
        raise CatalogError(f"{where}: driveLaneM must be a length in metres >= 0")


def _repair_list(where, m, key, items):
    if not isinstance(items, list) or not all(
            isinstance(r, dict) and set(r) <= {"param", "dir", "integer"}
            and (m["params"].get(r.get("param")) or {}).get("type") == "number"
            and r.get("dir", "down") in ("down", "up") and isinstance(r.get("integer", False), bool) for r in items):
        raise CatalogError(f"{where}: {key} is a list of {{param (a number param), dir down|up, integer?}}")


def _check_motion_rules(where, m):
    """engine/motion_rules.py manifest keys (phase 5 Chunk 5)."""
    if m.get("placement", "ground") not in ("ground", "float"):
        raise CatalogError(f"{where}: placement must be 'ground' or 'float'")
    for k in ("needsCameraMove", "vehicle"):
        if not isinstance(m.get(k, False), bool):
            raise CatalogError(f"{where}: {k} must be true or false")
    if m.get("standsOn") not in (None, "plinth"):
        raise CatalogError(f"{where}: standsOn is 'plinth' or absent")
    rc = m.get("rateCap")
    if rc is not None:
        if not (isinstance(rc, dict) and set(rc) <= {"degS", "repair"} and _is_num(rc.get("degS")) and rc["degS"] > 0):
            raise CatalogError(f"{where}: rateCap is {{degS > 0, repair: [...]}}")
        _repair_list(where, m, "rateCap.repair", rc.get("repair", []))
    _repair_list(where, m, "shorten", m.get("shorten", []))


def _check_physics(where, kind, m):
    if kind != "field":
        bad = [p for p in m["params"] if _WIND_PARAM.match(p)]
        if bad:
            raise CatalogError(f"{where}: only the wind field owns wind params, found {bad}")
    if kind == "world":
        if m.get("groundType", "studio") not in GROUND_TYPES:
            raise CatalogError(f"{where}: groundType must be one of {list(GROUND_TYPES)}")
        if not isinstance(m.get("hasFoliage", False), bool):
            raise CatalogError(f"{where}: hasFoliage must be true or false")
        wd = m.get("windDefault", 0.0)
        if not _is_num(wd) or not 0 <= wd <= 14:
            raise CatalogError(f"{where}: windDefault must be a wind speed in [0, 14] m/s")
        _check_world_phase5(where, m)
    if kind in ("effect", "motion", "camera"):
        mpc = m.get("maxPerClip")      # absent = unlimited; the phase-3 default uses several orbit/macro shots
        if mpc is not None and (not isinstance(mpc, int) or isinstance(mpc, bool) or mpc < 1):
            raise CatalogError(f"{where}: maxPerClip must be an integer >= 1")
    if kind == "camera":
        if not isinstance(m.get("constantSpeed", False), bool):
            raise CatalogError(f"{where}: constantSpeed must be true or false")
        if m.get("follows", "anchor") not in FOLLOWS:
            raise CatalogError(f"{where}: follows must be one of {list(FOLLOWS)}")
        if not isinstance(m.get("hookable", True), bool):
            raise CatalogError(f"{where}: hookable must be true or false")
        rm = m.get("requiresMotion", [])
        if not isinstance(rm, list) or not all(isinstance(x, str) for x in rm) or set(rm) - set(MOTION_FLAGS):
            raise CatalogError(f"{where}: requiresMotion must be a list from {list(MOTION_FLAGS)}")
    if kind == "motion":
        sm = m.get("subjectMotion", {})
        if (not isinstance(sm, dict) or set(sm) - set(MOTION_FLAGS)
                or not all(isinstance(v, bool) for v in sm.values())):
            raise CatalogError(f"{where}: subjectMotion maps {list(MOTION_FLAGS)} to true/false")
        dp = m.get("distanceParam")      # phase 5: the param checker._travel scales down (motion_travel_capped)
        if dp is not None and (m["params"].get(dp) or {}).get("type") != "number":
            raise CatalogError(f"{where}: distanceParam must name a number param")
        _check_motion_rules(where, m)
    if kind == "realism":
        # Task 12a: every realism block is always-on (alwaysOn may be omitted); it can never be chosen.
        if m.get("alwaysOn", True) is not True or m.get("directorSelectable", False) is not False:
            raise CatalogError(f"{where}: realism blocks are always on and never director-selectable")
        if "appliesWhen" in m:          # absent = applies to every subject (phase-3 test fixtures omit it)
            _check_applies(where, m["appliesWhen"])
        auto = m.get("autoParams", [])
        if not isinstance(auto, list) or set(auto) - set(m["params"]):
            raise CatalogError(f"{where}: autoParams must name params of this block")
    if kind == "field" and m["id"] != "wind":
        raise CatalogError(f"{where}: the only field is 'wind' (one shared wind per clip)")
    if "physics" in m:
        _check_physics_meta(where, m["physics"])


def _check_manifest(folder_kind, folder_id, m):
    where = f"{folder_kind}/{folder_id}"
    if not isinstance(m, dict):
        raise CatalogError(f"{where}: block.json must be an object")
    missing = [k for k in _REQUIRED if k not in m]
    if missing:
        raise CatalogError(f"{where}: missing keys {missing}")
    _check_types(where, m)
    if m["id"] != folder_id:
        raise CatalogError(f"{where}: id '{m['id']}' does not match folder '{folder_id}'")
    if m["kind"] != folder_kind:
        raise CatalogError(f"{where}: kind '{m['kind']}' does not match folder '{folder_kind}'")
    lo, hi = m["subjectSizeM"]
    if not 0 < lo <= hi:
        raise CatalogError(f"{where}: bad subjectSizeM")
    bad = [a for a in m["aspects"] if a not in ASPECTS]
    if bad:
        raise CatalogError(f"{where}: unknown aspects {bad}")
    for name, spec in m["params"].items():
        _check_param(where, name, spec)
    _check_physics(where, folder_kind, m)
    _check_director_fields(where, m)
    if folder_kind == "camera":
        lacking = [p for p in _CAMERA_PARAMS if p not in m["params"]]
        if m.get("framing") not in ("full", "detail") or lacking:
            raise CatalogError(f"camera '{folder_id}' missing framing or params {lacking}")
        if not m["params"]["distance"].get("min", 0) > 0:
            raise CatalogError(f"camera '{folder_id}': distance min must be > 0")
        if "move" in m:
            _check_move(folder_id, m)


def _has(profile, fact):
    """A profile fact is present; clips count only when measured with the current clip map (engine.clips)."""
    if fact == "animationClips":
        from engine.clips import clips_current
        return clips_current(getattr(profile, fact, None) or [])
    from engine.physics.shape import SHAPE_FACTS
    if fact in SHAPE_FACTS:                 # computed from surface samples (phase 5 Task 55), high only
        from engine.physics.shape import shape_facts
        return shape_facts(profile)[fact][0]
    return bool(getattr(profile, fact, None))


def _requires(m):
    """requiresProfile as a list: a string (phase-3 plan) or a list of profile facts (BLOCKS.md §1.1)."""
    req = m.get("requiresProfile", [])
    return [req] if isinstance(req, str) else req


def _check_director_fields(where, m):
    caps = m.get("capabilities", [])
    if not isinstance(caps, list) or not all(isinstance(c, str) and _CAP.match(c) for c in caps):
        raise CatalogError(f"{where}: capabilities must be a list of 'area.name' tags")
    if not isinstance(m.get("alwaysOn", False), bool):
        raise CatalogError(f"{where}: alwaysOn must be true or false")
    if not isinstance(m.get("directorSelectable", True), bool):
        raise CatalogError(f"{where}: directorSelectable must be true or false")
    req = _requires(m)
    if not isinstance(req, list) or not all(isinstance(r, str) and r in REQUIRES_PROFILE for r in req):
        raise CatalogError(f"{where}: requiresProfile must be one of {list(REQUIRES_PROFILE)} (or a list of them)")


def _always_on(kind, m):
    """Realism defaults the system adds (Task 12a): alwaysOn, or any block of kind realism (BLOCKS.md §1)."""
    return kind == "realism" or bool(m.get("alwaysOn"))


def _selectable(kind, m):
    """Blocks the director may choose: not harness-only controls (turntable), not always-on defaults."""
    return not _always_on(kind, m) and m.get("directorSelectable", True)


def _check_move(folder_id, m):
    """`move` is a CameraBench name, or {param, map} naming the move per value of an enum param
    (e.g. macro_detail: slide -> truck, push -> dolly)."""
    mv = m["move"]
    if isinstance(mv, dict):
        spec = m["params"].get(mv.get("param"))
        mp = mv.get("map")
        if (set(mv) != {"param", "map"} or not spec or spec.get("type") != "enum"
                or not isinstance(mp, dict) or set(mp) != set(spec["values"])):
            raise CatalogError(f"camera '{folder_id}': move map must name an enum param and map every value")
        names = list(mp.values())
    else:
        names = [mv]
    for name in names:
        if not isinstance(name, str) or name not in CAMERA_MOVES:
            raise CatalogError(f"camera '{folder_id}': move {name!r} not in {list(CAMERA_MOVES)}")


class Catalog:
    def __init__(self, blocks, root):
        self._blocks = blocks  # {(kind, id): manifest}
        self._root = root
        self._modules = {}  # {(kind, id, file): callable}
        self._module_objs = {}  # {(kind, id, file): module}: this catalog's own module (review chunk1 #7)

    @classmethod
    def load(cls, root=None):
        root = Path(root) if root else BLOCKS_DIR
        blocks = {}
        if root.is_dir():
            unknown = sorted(p.name for p in root.iterdir() if p.is_dir() and p.name not in KINDS)
            if unknown:
                raise CatalogError(f"{root}: unknown kind folder(s) {unknown}; expected {list(KINDS)}")
        for kind in KINDS:
            kdir = root / kind
            if not kdir.is_dir():
                continue
            for bdir in sorted(p for p in kdir.iterdir() if p.is_dir()):
                mf = bdir / "block.json"
                if not mf.is_file():
                    raise CatalogError(f"{kind}/{bdir.name}: missing block.json")
                try:
                    m = json.loads(mf.read_text(encoding="utf-8-sig"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
                    raise CatalogError(f"{kind}/{bdir.name}: bad block.json: {e}") from e
                _check_manifest(kind, bdir.name, m)
                blocks[(kind, bdir.name)] = m
        for (kind, bid), m in blocks.items():
            for eid in (m.get("appliesWhen") or {}).get("effects", []):
                if ("effect", eid) not in blocks:
                    raise CatalogError(f"{kind}/{bid}: appliesWhen.effects names unknown effect '{eid}'")
            ph = m.get("physics") or {}
            for key in ("couplings", "excludes"):
                for eid in ph.get(key, []):
                    if ("effect", eid) not in blocks:
                        raise CatalogError(f"{kind}/{bid}: physics.{key} names unknown effect '{eid}'")
            for lid in m.get("lightingPairs") or []:
                if kind == "world" and ("lighting", lid) not in blocks:
                    raise CatalogError(f"{kind}/{bid}: lightingPairs names unknown lighting '{lid}'")
            tsp = ph.get("timeScaleParam")
            if tsp is not None and tsp not in m["params"]:
                raise CatalogError(f"{kind}/{bid}: physics.timeScaleParam '{tsp}' is not one of its params")
        return cls(blocks, root)

    @property
    def root(self):
        return self._root

    def get(self, kind, bid):
        return copy.deepcopy(self._blocks.get((kind, bid)))

    def ids(self, kind):
        return [b for (k, b) in self._blocks if k == kind]

    def selectable_ids(self, kind):
        """Blocks the director may choose. Harness-only controls (turntable) set directorSelectable false."""
        return sorted(b for (k, b), m in self._blocks.items() if k == kind and _selectable(k, m))

    def always_on(self):
        return sorted((k, b) for (k, b), m in self._blocks.items() if _always_on(k, m))

    def applies(self, m, profile):
        """A block needing profile facts (requiresProfile) applies only when the profile has them all.
        profile=None: ignore the requirement."""
        return profile is None or all(_has(profile, r) for r in _requires(m))

    def capabilities(self, profile=None, script=None):
        """Tags the system can deliver for this profile: selectable blocks plus always-on realism blocks
        that apply (so an ask for tyre squish is not reported unsupported once that block exists).
        A selectable block counts only when its kind has a menu/script slot (menu.KIND_ORDER): the
        director cannot choose what the menu never shows. With a script (and a profile), an always-on
        block with appliesWhen counts only where engine.physics.applies.match holds for that script
        (hand-off H2: "make the tyres squish" on a floating subject is not delivered)."""
        from engine.director.menu import KIND_ORDER
        out = set()
        for (kind, bid), m in self._blocks.items():
            usable = _always_on(kind, m) or (kind in KIND_ORDER and m.get("directorSelectable", True))
            if usable and self.applies(m, profile) and self._applies_to(kind, m, profile, script):
                out |= set(m.get("capabilities", []))
        return out

    def _applies_to(self, kind, m, profile, script):
        if script is None or profile is None or not _always_on(kind, m) or "appliesWhen" not in m:
            return True
        from engine.physics.applies import match
        try:
            return match(m, script, profile, self)[0]
        except (KeyError, TypeError, AttributeError):   # a draft script without subject/world: profile only
            return True

    def _load_module(self, kind, bid, filename, attr):
        """Import engine/blocks/<kind>/<id>/<filename> and return its callable <attr>, cached per
        (kind, id, file). The id is guarded: no path separators, no '..', a known block."""
        if not isinstance(bid, str) or not bid or "/" in bid or "\\" in bid or ".." in bid:
            raise CatalogError(f"{kind} id {bid!r} is not a valid block id")
        key = (kind, bid, filename)
        if key in self._modules:
            return self._modules[key]
        if (kind, bid) not in self._blocks:
            raise CatalogError(f"unknown {kind} '{bid}'")
        f = self._root / kind / bid / filename
        if not f.is_file():
            raise CatalogError(f"{kind}/{bid}: missing {filename}")
        name = f"valora_{kind}_{bid}_{f.stem}"
        spec = importlib.util.spec_from_file_location(name, f)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod  # before exec: dataclasses, pickle and typing resolve the module by name
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            sys.modules.pop(name, None)
            raise CatalogError(f"{kind}/{bid}: {filename} failed to import: {e}") from e
        fn = getattr(mod, attr, None)
        if not callable(fn):
            raise CatalogError(f"{kind}/{bid}: {filename} has no callable {attr}()")
        self._modules[key] = fn
        self._module_objs[key] = mod
        return fn

    def _module_attr(self, kind, bid, filename, attr):
        """An optional callable from a block file this catalog loaded (never a same-named module another
        catalog root loaded later: sys.modules is global, this cache is per catalog)."""
        fn = getattr(self._module_objs.get((kind, bid, filename)), attr, None)
        return fn if callable(fn) else None

    def load_camera_path(self, bid):
        """Import engine/blocks/camera/<id>/path.py and return its sample() function."""
        return self._load_module("camera", bid, "path.py", "sample")

    def has_motion_path(self, bid):
        """True only when motion/<id>/ has a path.py (load_motion_path raises otherwise, so ask first).
        play_clip and fixture motions have none: they are the identity pose (engine/motion_path.py)."""
        if not isinstance(bid, str) or not bid or "/" in bid or "\\" in bid or ".." in bid:
            return False
        return ("motion", bid) in self._blocks and (self._root / "motion" / bid / "path.py").is_file()

    def load_motion_path(self, bid):
        """Import engine/blocks/motion/<id>/path.py and return its sample(params, profile, t, duration)."""
        return self._load_module("motion", bid, "path.py", "sample")

    def load_motion_flags(self, bid):
        """path.py's flags(params) (dynamic subjectMotion flags), or None when it defines none."""
        self.load_motion_path(bid)
        return self._module_attr("motion", bid, "path.py", "flags")

    def motion_still(self, bid, params):
        """The explicit identity contract (review chunk1 #2): True only when motion/<id>/path.py defines
        still(params) and it returns True for these params. A path.py without still() is a moving motion:
        sampling can never prove a pose function is the identity (a brief excursion between samples)."""
        if not self.has_motion_path(bid):
            return True
        self.load_motion_path(bid)
        fn = self._module_attr("motion", bid, "path.py", "still")
        return bool(fn(params or {})) if fn is not None else False

    def load_builder(self, kind, bid):
        """build.py's build(ctx). build.py must import bpy inside build(), never at module level."""
        return self._load_module(kind, bid, "build.py", "build")
