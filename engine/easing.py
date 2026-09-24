"""Easing curves shared by camera paths (checker) and the compiler. One definition, no drift.

TIERS T2-03: camera moves are eased; `linear` exists only for blocks that declare
`linearByDesign`. products.md P-C03 uses in_quad for a tension push."""

EASINGS = ("in_out_cubic", "smoothstep", "in_quad", "out_cubic", "linear")


def _clamp01(u):
    return 0.0 if u < 0 else 1.0 if u > 1 else float(u)


def ease(name, u):
    u = _clamp01(u)
    if name == "linear":
        return u
    if name == "in_quad":
        return u * u
    if name == "out_cubic":
        return 1.0 - (1.0 - u) ** 3
    if name == "smoothstep":
        return u * u * (3.0 - 2.0 * u)
    if name == "in_out_cubic":
        return 4.0 * u ** 3 if u < 0.5 else 1.0 - (-2.0 * u + 2.0) ** 3 / 2.0
    raise ValueError(f"unknown easing {name!r}")


def settle(u, settle_frac):
    """Map shot progress u to move progress so the move completes at 1 - settle_frac and then
    holds still (products.md P-E07: every move ends in true stillness). settle_frac is at most 0.5."""
    if settle_frac <= 0:
        return _clamp01(u)
    return _clamp01(u / (1.0 - settle_frac))
