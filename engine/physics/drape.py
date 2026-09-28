"""drape_reveal geometry (phase 6 Task 108; METHODS SC-02). Pure: the sheet's size and grid, its pre-shape over
the subject from a top-down height map, the pinned vertices, and the pull path of the hook that drags the sheet
off. engine/blocks/sim/drape_reveal/bake.py feeds it heights ray-cast onto the closed shell.

- Sheet: 1.5 x the footprint plus the height on each axis (so it reaches the ground on every side), at about
  1% of the subject per vertex, under the 8k-vertex budget (engine/physics/cloth.grid_dims).
- Collider: a height field of the shell seen from above (heightfield), two times finer than the sheet; the closed
  shell itself only judges the probe.
- Pre-shape (SC-02 "start above the proxy + small offset"): every vertex sits `offset` (2 shell voxels) above
  max(height, a dilated and blurred copy of the height map), so the sheet starts as a smooth tent that never
  touches the shell, sloping to the ground past the silhouette; the pre-roll lets it settle onto the subject.
- Pull: `side` drags the sheet's edge row on the camera's right across and away; `rear_to_front` drags the row
  at the nose end forward along the subject's long axis; `up` lifts a small patch at the top straight up.
  Two hands (GRIP_W of the edge each) ease in at PULL_START_S into the window, clear the subject by revealS, are a
  sheet-length past it by revealS + 0.5 (the probe's "off the subject" time), then keep walking out of frame. The side/rear pulls rise to
  LIFT x the subject height so the sheet lifts off rather than scrubbing the paint."""
import math

from engine.physics import cloth as C

PULL_START_S = 0.3      # (eng) the sheet rests this long into the window before the pull starts
LIFT = 1.6              # (eng) side / rear pulls rise to 1.6 x the subject height (lift off, not scrub)
DILATE = 2              # (eng) height-map dilation in cells (the tent over thin gaps)
BLUR = 3                # (eng) box-blur passes of the dilated map
UP_PATCH = 1.5          # (eng) cells: the lifted patch's radius for pull=up
GRIP_W = 0.15           # (eng) each hand holds 15% of the pulled edge
SIM_REF_M = 1.0         # subjects under 1 m are simulated at 1 m (sim_scale)
DROP_Z = 0.25           # (eng) after revealS + 0.5 the hands drop to 0.25 x the subject height and keep walking


def sim_scale(profile):
    """Blender cloth misbehaves at small scale: its solver tolerances are absolute, so a watch cover (0.8 mm
    vertices, forces scaled down by ~1e-3) stretched 7x where the car cover held. A subject under SIM_REF_M is
    simulated enlarged by SIM_REF_M / longest with gravity scaled the same (so it falls on real time) and
    written back at real size; the timing is kept, the solver sees metre-scale numbers."""
    return max(1.0, SIM_REF_M / max(profile.sizeM))


def sheet_size(profile):
    """(width along x, length along y) of the sheet: 1.5 x footprint + height."""
    sx, sy, sz = profile.sizeM
    return 1.5 * sx + sz, 1.5 * sy + sz


def sheet_grid(profile):
    """(nx, ny, spacing, width, length, centre (x, y))."""
    w, l = sheet_size(profile)
    nx, ny, sp = C.grid_dims(w, l, C.spacing_m(max(profile.sizeM)))
    bmin, bmax = profile.boundsMin, profile.boundsMax
    return nx, ny, sp, (nx - 1) * sp, (ny - 1) * sp, ((bmin[0] + bmax[0]) / 2, (bmin[1] + bmax[1]) / 2)


def grid_xy(nx, ny, sp, centre):
    w, l = (nx - 1) * sp, (ny - 1) * sp
    return [(centre[0] - w / 2 + i * sp, centre[1] - l / 2 + j * sp) for j in range(ny) for i in range(nx)]


def _dilate(h, nx, ny, r):
    out = list(h)
    for j in range(ny):
        for i in range(nx):
            m = h[j * nx + i]
            for dj in range(-r, r + 1):
                for di in range(-r, r + 1):
                    a, b = i + di, j + dj
                    if 0 <= a < nx and 0 <= b < ny:
                        m = max(m, h[b * nx + a])
            out[j * nx + i] = m
    return out


def _blur(h, nx, ny):
    out = list(h)
    for j in range(ny):
        for i in range(nx):
            s, n = 0.0, 0
            for dj in (-1, 0, 1):
                for di in (-1, 0, 1):
                    a, b = i + di, j + dj
                    if 0 <= a < nx and 0 <= b < ny:
                        s += h[b * nx + a]
                        n += 1
            out[j * nx + i] = s / n
    return out


def preshape(heights, nx, ny, offset):
    """z per vertex: `offset` above max(height, blur^BLUR(dilate(height))). Never below height + offset."""
    t = _dilate(heights, nx, ny, DILATE)
    for _ in range(BLUR):
        t = _blur(t, nx, ny)
    return [max(h, s) + offset for h, s in zip(heights, t)]


def heightfield(heights, nx, ny, dilate=1, blur=2):
    """The collider's z per vertex: the shell's top-down height map grown by `dilate` cells. A cover sees the
    subject from above: the height field has no undercuts, so the sheet cannot hook into a wheel arch or a
    handle recess (a snag stretched a silk sheet 13x on the sports car against the closed shell), and it
    encloses the shell, so a sheet outside it is outside the subject."""
    t = _dilate(heights, nx, ny, dilate)
    s = t
    for _ in range(blur):                  # a cliff one cell wide caught an edge vertex (stretch 3-4x at the
        s = _blur(s, nx, ny)               # nose corner); a short slope lets the sheet slide over it
    return [max(a, b) for a, b in zip(t, s)]


def pull_dir(pull, profile, camera_xy=None, nose_sign=1):
    """Unit horizontal (x, y) the hook moves along; (0, 0) for `up`. `side` is the camera's right (or +x when
    there is no camera); `rear_to_front` is along the long horizontal axis toward the nose."""
    if pull == "up":
        return (0.0, 0.0)
    sx, sy = profile.sizeM[0], profile.sizeM[1]
    if pull == "rear_to_front":
        return (float(nose_sign), 0.0) if sx >= sy else (0.0, float(nose_sign))
    short = (1.0, 0.0) if sx < sy else (0.0, 1.0)           # across the subject: its short horizontal axis
    if camera_xy is None:
        return short
    cx = (profile.boundsMin[0] + profile.boundsMax[0]) / 2
    cy = (profile.boundsMin[1] + profile.boundsMax[1]) / 2
    vx, vy = cx - camera_xy[0], cy - camera_xy[1]           # the camera's view direction; its right is (vy, -vx)
    sign = 1.0 if short[0] * vy - short[1] * vx >= 0 else -1.0
    return (short[0] * sign, short[1] * sign)               # toward the camera's right hand


def pins(pull, nx, ny, xy, zs, direction):
    """Vertex indices the hook holds: the edge row farthest along the pull direction, or for `up` a small patch
    around the highest vertex."""
    if pull == "up":
        top = max(range(nx * ny), key=lambda k: (zs[k], -abs(k % nx - nx / 2) - abs(k // nx - ny / 2)))
        ti, tj = top % nx, top // nx
        return [j * nx + i for j in range(ny) for i in range(nx) if math.hypot(i - ti, j - tj) <= UP_PATCH]
    dx, dy = direction
    if abs(dx) >= abs(dy):
        i = nx - 1 if dx > 0 else 0
        return [j * nx + i for j in _grips(ny)]
    j = ny - 1 if dy > 0 else 0
    return [j * nx + i for i in _grips(nx)]


def _grips(n):
    """Two hands on the edge: GRIP_W of its length each, centred at 1/4 and 3/4 (a whole edge held straight
    rose as a rigid board in the first car clip); at least 2 vertices per hand."""
    half = max(1, int(round(GRIP_W * (n - 1) / 2)))
    out = set()
    for c in (round((n - 1) / 4), round(3 * (n - 1) / 4)):
        out.update(k for k in range(c - half, c + half + 1) if 0 <= k < n)
    return sorted(out)


def _ease(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def pull_keys(pull, profile, start_frame, fps, reveal_s, direction, sheet_wl, anchor, end_s=None):
    """[(frame, (dx, dy, dz))]: the hook's offset from its rest point, keyed every frame from the window start to
    end_s (default revealS + 0.5). After revealS + 0.5 the hands keep walking away at their pace (side / rear:
    dropping to DROP_Z x the subject height, so the sheet leaves the frame instead of hanging in it). One
    continuous path, never a jump (the lane R collider finding)."""
    sx, sy, sz = profile.sizeM
    w, l = sheet_wl
    t0 = PULL_START_S
    t1 = max(t0 + 0.5, reveal_s)
    t2 = t1 + 0.5
    if pull == "up":
        dist = sz + 0.6 * max(w, l)            # the sheet hangs about half its size below the lifted patch
    else:                                      # the trailing edge, a sheet-length behind the hook, clears the far side
        dist = abs(direction[0]) * (w + 0.25 * sx) + abs(direction[1]) * (l + 0.25 * sy)
    lift = LIFT * sz - anchor[2] if pull != "up" else 0.0
    keys = []
    last = int(math.ceil(t2 * fps)) if end_s is None else max(int(math.ceil(t2 * fps)), int(math.ceil(end_s * fps)))
    tail_v = 0.15 * dist / (t2 - t1)                   # the walking speed they keep after revealS + 0.5
    for k in range(0, last + 1):
        t = k / fps
        # 85% of the distance by revealS, the rest by revealS + 0.5, then they keep walking away at that pace
        if t <= t0:
            s = 0.0
        elif t <= t1:
            s = 0.85 * _ease((t - t0) / (t1 - t0))
        elif t <= t2:
            s = 0.85 + 0.15 * (t - t1) / (t2 - t1)
        else:
            s = 1.0 + tail_v * (t - t2) / dist
        if pull == "up":
            off = (0.0, 0.0, s * dist)
        else:
            rise = _ease((t - t0) / (0.6 * (t1 - t0))) if t > t0 else 0.0
            drop = _ease((t - t2) / 0.6) if t > t2 else 0.0
            z = rise * lift + drop * (DROP_Z * sz - anchor[2] - lift)
            off = (direction[0] * s * dist, direction[1] * s * dist, z)
        keys.append((start_frame + k, off))
    return keys


def off_subject_share(points, profile, margin=0.02):
    """Share of points inside the subject's bounds grown by `margin` x longest (0 = fully off)."""
    lo, hi = profile.boundsMin, profile.boundsMax
    m = margin * max(profile.sizeM)
    inside = sum(1 for p in points if all(lo[k] - m <= p[k] <= hi[k] + m for k in range(3)))
    return inside / len(points) if points else 0.0
