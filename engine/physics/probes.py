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


def tyre_patch_ok(rec, radius, patch_len_frac, sink_m, tol=PATCH_TOL):
    want = patch_len_frac * radius
    return (PATCH_MIN * want <= rec["flatLenM"] <= (1 + tol) * want
            and rec["minZ"] >= -sink_m - contact.GROUND_TOL_M)


# ---- weather (plan Task 69; BLOCKS §5 no_particles_in_subject, METHODS R7, PH-05) ----
PARTICLE_TOL = 0.001     # (eng) share of weather points allowed inside the posed subject bounds
STREAK_TOL = 0.4         # (eng) PH-05: a streak within +/-40% of speed x shutter time


def particles_inside_share(inside_by_frame, total_by_frame):
    total = sum(total_by_frame.values())
    return (sum(inside_by_frame.values()) / total) if total else 0.0


def no_particles_in_subject(points_by_frame, bounds_by_frame, tol=PARTICLE_TOL):
    """(ok, share): the share of points strictly inside their frame's posed bounds must be <= tol."""
    inside, total = {}, {}
    for f, pts in points_by_frame.items():
        lo, hi = bounds_by_frame[f]
        total[f] = len(pts)
        inside[f] = sum(1 for p in pts if all(lo[i] < p[i] < hi[i] for i in range(3)))
    share = particles_inside_share(inside, total)
    return share <= tol, share


def velocity_present(has_attr_by_object):
    """Every point-emitting weather object carries a velocity attribute (METHODS R7); none present = None."""
    return all(has_attr_by_object.values()) if has_attr_by_object else None


def streak_ok(len_px, speed, shutter, fps, px_per_m, tol=STREAK_TOL):
    want = speed * shutter / fps * px_per_m
    return want > 0 and abs(len_px - want) <= tol * want
