"""Which realism blocks apply to a script, and with which params (research/physics/BLOCKS.md §1:
compiler-added, never chosen by the director). The checker calls resolve_wind and resolve_realism
after validation. Every decision is an `info` issue: nothing here is an error, so it costs the director
no repair round and needs no repair hint (phase-3 Task 24 drift test)."""
from engine.compiler.context import block_seed
from engine.issues import Issue
from engine.physics import contact, suspension

# Build order = modifier stack order: body motion, then wheel spin, then the tyre flatten (a spinning
# wheel keeps its patch at the bottom, METHODS CD-02); object-level settle after the deformers.
ORDER = ("contact_ground", "suspension", "wheel_roll", "tyre_contact", "soft_rest", "landing_settle",
         "dangling_sway", "foliage_sway", "ground_conform", "shaft_dust", "glass_caustics")


def facts(profile):
    """{fact: (present at high confidence, present only at low confidence)} for catalog.PROFILE_FACTS."""
    ws, soft, dang = profile.wheels or [], profile.softParts or [], profile.danglingParts or []
    wheels_high = bool(ws) and all(w.get("confidence") == "high" for w in ws)
    low_w = bool(ws) and not wheels_high
    soft_high = any(s.get("confidence") == "high" for s in soft)
    soft_ground = any(s.get("confidence") == "high" and s.get("touchesGround") for s in soft)
    dang_high = any(d.get("confidence") == "high" for d in dang)
    return {
        "wheels": (wheels_high, low_w),
        "wheelsSeparable": (wheels_high and all(w.get("separable") for w in ws), low_w),
        "tyreBand": (wheels_high and all(w.get("tyreBand") and w.get("width") for w in ws), low_w),
        "bodySeparable": (wheels_high and bool((profile.vehicle or {}).get("bodySeparable")), low_w),
        "softParts": (soft_high, bool(soft) and not soft_high),
        "softGround": (soft_ground, any(s.get("touchesGround") for s in soft) and not soft_ground),
        "danglingParts": (dang_high, bool(dang) and not dang_high),
    }


def match(m, s, profile, catalog):
    """(applies, reason, skipped_for_low_confidence)."""
    aw, fx, why, low_reason = m.get("appliesWhen", {}), facts(profile), [], None
    pl = s["subject"].get("placement")
    if "placement" in aw:
        if pl not in aw["placement"]:
            return False, f"placement {pl}", False
        why.append(f"placement {pl}")
    for name in aw.get("profile", []):
        ok, low = fx[name]
        if not ok and not low:
            return False, f"profile {name} absent", False
        if not ok and low_reason is None:   # reported only if nothing else rules the block out
            low_reason = f"profile {name} is low confidence"
        why.append(f"profile {name}")
    for name in aw.get("profileNot", []):
        if fx[name][0]:
            return False, f"profile has {name}", False
    world = catalog.get("world", s["world"]["id"]) or {}
    w, gt = aw.get("world", {}), world.get("groundType", "studio")
    if "groundType" in w:
        if gt not in w["groundType"]:
            return False, f"ground {gt}", False
        why.append(f"ground {gt}")
    if "hasFoliage" in w and bool(world.get("hasFoliage", False)) != w["hasFoliage"]:
        return False, "world foliage", False
    if aw.get("motion"):
        flags = (catalog.get("motion", s["subject"]["motion"]["id"]) or {}).get("subjectMotion") or {}
        hit = [k for k in aw["motion"] if flags.get(k)]
        if not hit:
            return False, "the subject never " + "/".join(aw["motion"]), False
        why.append("motion " + "/".join(hit))
    if aw.get("effects"):
        present = {fx_["id"] for fx_ in s.get("effects", []) if isinstance(fx_, dict)}
        hit = [e for e in aw["effects"] if e in present]
        if not hit:
            return False, "no " + "/".join(aw["effects"]), False
        why.append("effect " + "/".join(hit))
    shares = {x["class"]: x["share"] for x in profile.materials}
    for cls, lo in aw.get("materials", {}).items():
        if shares.get(cls, 0.0) < lo:
            return False, f"{cls} share {shares.get(cls, 0.0):.3f} < {lo}", False
        why.append(f"{cls} share {shares[cls]:.3f}")
    if "sizeM" in aw and not aw["sizeM"][0] <= profile.longest <= aw["sizeM"][1]:
        return False, f"size {profile.longest:.3f} m outside {aw['sizeM']}", False
    if low_reason:
        return False, low_reason, True
    return True, "; ".join(why) or "always", False


def _auto_contact(profile, s, world):
    return {"sinkMm": 1000.0 * contact.sink_m(world.get("groundType", "studio"), profile.sizeM[2])}


def _auto_suspension(profile, s, world):
    return {"rideHz": suspension.ride_hz((profile.vehicle or {}).get("vehicleClass", "comfort"))}


def _auto_landing(profile, s, world):
    return {"squash": 0.92 if facts(profile)["softParts"][0] else 1.0}   # CD-04: soft goods squash 5-15%


AUTO = {"contact_ground": _auto_contact, "suspension": _auto_suspension,   # block id -> auto params
        "landing_settle": _auto_landing}


def _guard_contact(profile, params):
    return {"sinkMm": min(params["sinkMm"], 1000.0 * contact.MAX_SINK_FRAC * profile.sizeM[2])}


# Safety caps that hold for auto AND pinned values (a pin is a preference, never a way past physics).
GUARDS = {"contact_ground": _guard_contact}


def _pins(ref):
    """The params a script really pinned. A resolved entry lists them in `pinned`; the rest of its params
    are system output and are resolved again (a re-check after a world change must not freeze them)."""
    params = ref.get("params") or {}
    if "pinned" in ref and isinstance(ref["pinned"], list):
        return {k: params[k] for k in ref["pinned"] if k in params}
    return params


def _valid(spec, v):
    t = spec["type"]
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool) and spec["min"] <= v <= spec["max"]
    if t == "enum":
        return v in spec["values"]
    return isinstance(v, bool)


def resolve_realism(s, profile, catalog, issues):
    given = {r["id"]: r for r in s.get("realism", []) if isinstance(r, dict) and r.get("kind") == "realism"}
    other = [r for r in s.get("realism", []) if isinstance(r, dict) and r.get("kind") != "realism"]
    world = catalog.get("world", s["world"]["id"]) or {}
    ids = [b for b in ORDER if b in catalog.ids("realism")]
    ids += sorted(set(catalog.ids("realism")) - set(ORDER))
    out = []
    for bid in ids:
        m = catalog.get("realism", bid)
        ok, reason, low = match(m, s, profile, catalog)
        if not ok:
            if low:
                issues.append(Issue("realism_skipped_low_confidence", f"realism.{bid}", reason, "info"))
            if bid in given:
                issues.append(Issue("realism_not_applicable", f"realism.{bid}", reason, "info"))
            continue
        specs = m["params"]
        params = {k: sp["default"] for k, sp in specs.items()}
        auto = AUTO[bid](profile, s, world) if bid in AUTO else {}
        for k in m.get("autoParams", []):
            if k in auto:   # a name AUTO cannot compute keeps its default (never a crash inside check)
                params[k] = float(min(max(auto[k], specs[k]["min"]), specs[k]["max"]))
        pinned = []
        for k, v in _pins(given.get(bid, {})).items():
            if k in specs and _valid(specs[k], v):
                params[k] = v
                pinned.append(k)
            else:
                issues.append(Issue("realism_param_ignored", f"realism.{bid}.params.{k}",
                                    f"{v!r} is not a valid {k}", "info"))
        for k, v in (GUARDS[bid](profile, params) if bid in GUARDS else {}).items():
            if v != params[k]:
                issues.append(Issue("realism_param_capped", f"realism.{bid}.params.{k}",
                                    f"{params[k]!r} capped to {v!r} for this subject", "info"))
                params[k] = v
        out.append({"kind": "realism", "id": bid, "params": params, "reason": reason, "pinned": pinned})
        issues.append(Issue("realism_applied", f"realism.{bid}", reason, "info"))
    res = other + out
    if res:
        s["realism"] = res
    else:
        s.pop("realism", None)


def resolve_wind(s, catalog, issues):
    """One wind per clip. A valid script wind is kept; otherwise the world's still-air default, with a
    seeded direction (calm unless the script asks)."""
    m = catalog.get("field", "wind")
    if m is None:
        return
    w = s.get("wind") if isinstance(s.get("wind"), dict) and s["wind"].get("id") == "wind" else None
    if w is not None and "pinned" not in w:   # a hand-written wind: every param it carries is the script's
        w["pinned"] = sorted(w.get("params") or {})
        issues.append(Issue("wind_from_script", "wind", f"{w['params'].get('speedMs')} m/s", "info"))
        return
    pins = _pins(w) if w is not None else {}   # a resolved wind: only its real pins survive a re-check
    world = catalog.get("world", s["world"]["id"]) or {}
    params = {k: sp["default"] for k, sp in m["params"].items()}
    params["speedMs"] = float(world.get("windDefault", params["speedMs"]))
    params["directionDeg"] = float(block_seed(s["seed"], "field", "wind") % 360)
    params.update(pins)
    s["wind"] = {"id": "wind", "params": params, "pinned": sorted(pins)}
    if pins:
        issues.append(Issue("wind_from_script", "wind", f"{params['speedMs']} m/s", "info"))
    else:
        issues.append(Issue("wind_defaulted", "wind", f"{params['speedMs']} m/s from world {s['world']['id']}", "info"))
