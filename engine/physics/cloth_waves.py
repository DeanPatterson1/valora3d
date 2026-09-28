"""Stateless cloth (phase 6 Task 109; METHODS SC-01 flag, SC-05 silk ribbon). Pure: vertex positions as a
function of time, keyed per frame by engine/blender/cloth.shape_sequence (no simulation, bake.method "none").

Flag (SC-01): a real-size flag on a real-size pole (scale cues stay real-size, METHODS R4/R5). The mean plane
leans from hanging (calm) toward the downwind horizontal by the quasi-static drag angle of Task 107
(engine/physics/cloth.drag_angle_deg, nylon ~0.11 kg/m2); a travelling wave runs from the pole to the fly end,
amplitude growing from zero at the pole, frequency rising with the wind speed, with a seeded second harmonic and
a slow gust envelope so it never reads as a perfect sine.

Silk ribbon (SC-05): a band flowing along a closed path around the subject, OUTSIDE its bounds plus a margin (an
ellipse through the footprint's corners, grown by the margin and half the ribbon width), lower on the camera's
side so it passes under the product's hero face and higher behind; a travelling twist and a width modulation
at 3-10% of the subject height.

Every number is (eng) until the owner grades G8."""
import math

from engine.physics.cloth import drag_angle_deg

# ---- flag
FLAG_W, FLAG_H = 1.5, 0.9          # m: a 3:5 flag (eng; a common courtesy-flag size)
POLE_H = (2.5, 6.0)                 # m: a real pole, 2.2 x the subject's height within this range (eng)
POLE_R = 0.025                      # m
FLAG_AREAL = 0.11                   # kg/m2: flag nylon (eng)
FLAG_NX, FLAG_NY = 38, 23           # ~4 cm vertices
WAVELENGTH_FRAC = 0.55              # about two waves along the flag at any speed (eng; a longer wave
                                    # read as a flat board flapping in the first field clip)
FLUTTER_K = 0.35                    # flutter frequency f = 0.35 v / chord Hz (eng; rises with the wind)
AMP_FRAC = 0.11                     # peak normal amplitude at the fly end, x flag length (eng)
CALM_MS = 0.3                       # below this the flag just hangs


def flag_grid():
    """Rest (u, v) per vertex: u from the pole (0) to the fly end (FLAG_W), v from the top (0) down (FLAG_H)."""
    return [(i * FLAG_W / (FLAG_NX - 1), j * FLAG_H / (FLAG_NY - 1)) for j in range(FLAG_NY) for i in range(FLAG_NX)]


def flag_faces():
    nx = FLAG_NX
    return [(j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i)
            for j in range(FLAG_NY - 1) for i in range(nx - 1)]


def flag_frequency(speed_ms):
    return FLUTTER_K * max(speed_ms, 0.0) / FLAG_W


def pole_height(profile):
    return min(POLE_H[1], max(POLE_H[0], 2.2 * profile.sizeM[2]))


def flag_positions(t, speed_ms, direction_deg, pole_xy, seed, pole_h=POLE_H[0]):
    """World positions at time t (s). The pole stands at pole_xy; the flag's top edge hangs 5 cm under its top."""
    a = math.radians(direction_deg)
    wx, wy = math.cos(a), math.sin(a)                   # downwind
    nxv, nyv = -wy, wx                                  # the flag's horizontal normal
    theta = math.radians(drag_angle_deg(speed_ms, FLAG_AREAL)) if speed_ms > CALM_MS else 0.0
    top = pole_h - 0.05
    f = flag_frequency(speed_ms)
    k = 2 * math.pi / (WAVELENGTH_FRAC * FLAG_W)
    ph = (seed % 997) / 997.0 * 2 * math.pi
    gust = 0.8 + 0.2 * math.sin(2 * math.pi * 0.23 * t + ph) * math.sin(2 * math.pi * 0.071 * t + 2 * ph)
    amp = AMP_FRAC * FLAG_W * (0.35 + 0.65 * math.sin(theta)) * gust
    out = []
    for u, v in flag_grid():
        along, down = u * math.sin(theta), u * math.cos(theta)
        s = u / FLAG_W
        d = amp * s * (math.sin(k * u - 2 * math.pi * f * t + 1.2 * v / FLAG_H + ph)
                       + 0.3 * math.sin(2.1 * k * u - 4.3 * math.pi * f * t + 1.7 * ph))
        droop = 0.04 * s * s * FLAG_W * math.cos(theta)  # the fly end sags a little
        out.append((pole_xy[0] + wx * along + nxv * d, pole_xy[1] + wy * along + nyv * d,
                    top - v - down - droop))
    return out


def flag_pole_xy(profile, camera_xy, direction_deg):
    """Behind the subject from the camera, to one side, clear of it by a flag length, so the flag (which blows
    downwind up to FLAG_W from the pole) never crosses the subject's footprint."""
    cx = (profile.boundsMin[0] + profile.boundsMax[0]) / 2
    cy = (profile.boundsMin[1] + profile.boundsMax[1]) / 2
    vx, vy = (cx - camera_xy[0], cy - camera_xy[1]) if camera_xy is not None else (0.0, 1.0)
    n = math.hypot(vx, vy) or 1.0
    vx, vy = vx / n, vy / n
    r = 0.5 * math.hypot(profile.sizeM[0], profile.sizeM[1]) + FLAG_W + 0.5
    return (cx + vx * r * 1.2 - vy * r * 0.6, cy + vy * r * 1.2 + vx * r * 0.6)


def clear_of_subject(points, profile, margin=0.02):
    lo, hi = profile.boundsMin, profile.boundsMax
    m = margin * max(profile.sizeM)
    return not any(all(lo[i] - m <= p[i] <= hi[i] + m for i in range(3)) for p in points)


# ---- silk ribbon
RIBBON_N = 160                      # vertices along the band
RIBBON_LEN = 0.7                    # the band covers 70% of its loop
RIBBON_TWIST = 3.0                  # half-turns along the band
MARGIN_FRAC = 0.12                  # clearance outside the footprint, x longest


def ribbon_loop(profile, width, camera_xy=None):
    """(centre, a, b, zc, tilt, cam_angle): an ellipse through the footprint corners grown by the margin and half
    the width, centred at mid height, tilted so its camera side is lower."""
    cx = (profile.boundsMin[0] + profile.boundsMax[0]) / 2
    cy = (profile.boundsMin[1] + profile.boundsMax[1]) / 2
    sx, sy, sz = profile.sizeM
    grow = MARGIN_FRAC * max(sx, sy, sz) + width / 2
    a, b = sx / 2 * math.sqrt(2) + grow, sy / 2 * math.sqrt(2) + grow
    cam = math.atan2(camera_xy[1] - cy, camera_xy[0] - cx) if camera_xy is not None else -math.pi / 2
    return (cx, cy), a, b, 0.55 * sz, 0.25 * sz, cam


def ribbon_positions(t, profile, width_frac, flow_laps_s, seed, camera_xy=None):
    """(verts, faces): the band at time t, RIBBON_N x 2 vertices."""
    sz = profile.sizeM[2]
    width = width_frac * sz
    (cx, cy), a, b, zc, tilt, cam = ribbon_loop(profile, width, camera_xy)
    ph = (seed % 991) / 991.0 * 2 * math.pi
    head = 2 * math.pi * flow_laps_s * t + ph
    verts = []
    for i in range(RIBBON_N):
        s = i / (RIBBON_N - 1)
        ang = head - s * RIBBON_LEN * 2 * math.pi
        x, y = cx + a * math.cos(ang), cy + b * math.sin(ang)
        z = zc - tilt * math.cos(ang - cam) + 0.08 * sz * math.sin(3 * ang + ph)
        tx, ty = -a * math.sin(ang), b * math.cos(ang)
        n = math.hypot(tx, ty) or 1.0
        rx, ry = ty / n, -tx / n                          # outward horizontal
        twist = math.pi * RIBBON_TWIST * s + 2 * math.pi * 0.4 * t + ph
        w = width * (0.75 + 0.25 * math.sin(2 * math.pi * (2 * s - 0.3 * t) + ph)) * min(1.0, 4 * s, 4 * (1 - s) + 0.35)
        # the band's cross direction turns in the (outward, up) plane: it can lie flat but never pierce inward
        ox, oz = abs(math.cos(twist)), math.sin(twist)
        hw = w / 2
        verts.append((x - rx * ox * hw, y - ry * ox * hw, z - oz * hw))
        verts.append((x + rx * ox * hw, y + ry * ox * hw, z + oz * hw))
    faces = [(2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2) for i in range(RIBBON_N - 1)]
    return verts, faces
