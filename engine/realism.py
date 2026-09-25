"""Always-on realism defaults (owner 2026-09-24): blocks the system adds when they apply to the
subject, never chosen by the LLM. Pure; the director fills script["realism"] from this and the
compiler builds those blocks after effects."""


def realism_defaults(profile, catalog):
    out = []
    for kind, bid in catalog.always_on():
        m = catalog.get(kind, bid)
        if catalog.applies(m, profile):
            out.append({"kind": kind, "id": bid, "params": {k: s["default"] for k, s in m["params"].items()}})
    return out
