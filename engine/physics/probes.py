"""Pass rules for the compile-probe records (research/physics/BLOCKS.md §5 [C]). Report-only until
calibrated on golden renders (spec §4.8: thresholds are calibrated before they gate anything)."""
from engine.physics import contact

PATCH_TOL = 0.2          # flat length at most +20% of patchLenFrac * r (BLOCKS §5, eng)
PATCH_MIN = 0.6          # and at least 60%: the vertex extent of a coarse tyre (64 segments) reads up to
                         # one segment chord short depending on the wheel's angle (eng; Task 15 measures)


def grounded_ok(rec, sink_m, height=None):
    """With the subject's height, the gap tolerance tightens to contact.gap_tol(height)."""
    tol = contact.GROUND_TOL_M if height is None else contact.gap_tol(height)
    return contact.grounded(rec["minZ"], sink_m, tol)


def tyre_patch_ok(rec, radius, patch_len_frac, sink_m):
    want = patch_len_frac * radius
    return (PATCH_MIN * want <= rec["flatLenM"] <= (1 + PATCH_TOL) * want
            and rec["minZ"] >= -sink_m - contact.GROUND_TOL_M)
