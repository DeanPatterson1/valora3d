"""Always-on realism defaults (owner 2026-09-24): blocks the system adds when they apply to the
subject, never chosen by the LLM. Pure; the director fills script["realism"] from this and the
compiler builds those blocks after effects."""


def realism_defaults(profile, catalog, script=None):
    """Task 12a contract. With a checked-shape script, the exact list the checker will resolve
    (engine/physics/applies.py); without one, the profile-only rule below (phase-3 callers)."""
    if script is not None:
        import copy
        from engine.physics.applies import resolve_realism
        s = copy.deepcopy(script)
        resolve_realism(s, profile, catalog, [])
        return s.get("realism", [])
    out = []
    for kind, bid in catalog.always_on():
        m = catalog.get(kind, bid)
        if catalog.applies(m, profile):
            # kind realism: no params -> nothing pinned, so the checker's auto params (sink by ground,
            # ride frequency by class) are not overridden by defaults written by sanitize/fallback.
            params = {} if kind == "realism" else {k: sp["default"] for k, sp in m["params"].items()}
            out.append({"kind": kind, "id": bid, "params": params})
    return out
