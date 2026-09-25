"""Wheel angle from the subject's path: rolling without slip (TAXONOMY VD-02). The angular velocity of
a wheel rolling with velocity v on a ground with normal z is omega = (z x v) / r; its component along
the axle is the spin. The Blender wheel_roll block rotates each spinning island about its axle by
this angle (right-hand rule), so the contact point stays still on the ground."""
import math


def wheel_angles(pos, yaws, axle, radius, shots=None):
    """Cumulative angle (radians) per frame. pos: subject positions per frame (world); yaws: the motion
    empty's yaw per frame (radians); axle: the wheel's axle in placed space. shots (motion_path.frame_shots):
    a step between two takes (a perShot replay jumps back there) is never integrated; it turns at the mean of
    its in-take neighbours' steps, so the frame either side of a cut spins at an in-take rate."""
    steps = []
    for i in range(1, len(pos)):
        dx, dy = pos[i][0] - pos[i - 1][0], pos[i][1] - pos[i - 1][1]
        c, s = math.cos(yaws[i]), math.sin(yaws[i])
        ax, ay = c * axle[0] - s * axle[1], s * axle[0] + c * axle[1]
        steps.append((-dy * ax + dx * ay) / radius)
    cut = [shots is not None and shots[i + 1] != shots[i] for i in range(len(steps))]
    for i in (i for i, c in enumerate(cut) if c):
        near = [steps[j] for j in (i - 1, i + 1) if 0 <= j < len(steps) and not cut[j]]
        steps[i] = sum(near) / len(near) if near else 0.0
    out = [0.0]
    for d in steps:
        out.append(out[-1] + d)
    return out


def _cut(shots, i):
    """True when the step into index i crosses a cut (shots: motion_path.frame_shots)."""
    return shots is not None and shots[i] != shots[i - 1]


def _rolled(angles, radius, shots):
    """Metres the wheel rolled, take by take (a cut's filler step is no take's roll)."""
    from engine.physics.events import takes
    return sum(abs(angles[i1 - 1] - angles[i0]) for i0, i1 in takes(shots, len(angles))) * radius


def slip(angles, pos, radius, shots=None):
    """|rolled distance - travelled distance| / travelled (0 = no slip). Straight paths only. shots: per take."""
    path = sum(math.dist(pos[i], pos[i - 1]) for i in range(1, len(pos)) if not _cut(shots, i))
    return abs(_rolled(angles, radius, shots) - path) / path if path else 0.0


def contact_points(pos, yaws, contact):
    """World contact-point track of one wheel: the motion empty's location + its yaw applied to the wheel's
    placed contact point (the wheel centre minus r straight down)."""
    out = []
    for (x, y, z), yw in zip(pos, yaws):
        c, s = math.cos(yw), math.sin(yw)
        out.append((x + c * contact[0] - s * contact[1], y + s * contact[0] + c * contact[1], z + contact[2]))
    return out


def wheel_angles_contact(contact_pos, yaws, axle, radius, shots=None):
    """Curvature-aware wheel angles (hand-off H5): integrate each wheel's OWN contact-point path, so on an arc
    the outer wheel turns more than the inner one. contact_pos: this wheel's world contact point per frame."""
    return wheel_angles(contact_pos, yaws, axle, radius, shots)


def _rolling(contact_pos, yaws, axle, shots=None):
    """(rolling, lateral) metres of a contact path: each step split into the part across the axle (the wheel
    rolls it) and the part along it (scrub: an unsteered wheel pushed sideways on a turn)."""
    roll = side = 0.0
    for i in range(1, len(contact_pos)):
        if _cut(shots, i):
            continue
        dx, dy = contact_pos[i][0] - contact_pos[i - 1][0], contact_pos[i][1] - contact_pos[i - 1][1]
        c, s = math.cos(yaws[i]), math.sin(yaws[i])
        ax, ay = c * axle[0] - s * axle[1], s * axle[0] + c * axle[1]
        n = math.hypot(ax, ay) or 1.0
        roll += abs(-dy * ax / n + dx * ay / n)
        side += abs((dx * ax + dy * ay) / n)
    return roll, side


def slip_curved(angles, contact_pos, radius, yaws=None, axle=None, shots=None):
    """|rolled - travelled| / travelled on this wheel's own contact path (0 = no slip), any path shape. With the
    yaws and the axle, travelled is the rolling part of the path (the part along the axle is scrub(), not
    slip: phase 5 does not steer the front wheels)."""
    if yaws is not None and axle is not None:
        path = _rolling(contact_pos, yaws, axle, shots)[0]
    else:
        path = sum(math.hypot(contact_pos[i][0] - contact_pos[i - 1][0], contact_pos[i][1] - contact_pos[i - 1][1])
                   for i in range(1, len(contact_pos)) if not _cut(shots, i))
    return abs(_rolled(angles, radius, shots) - path) / path if path else 0.0


def scrub(contact_pos, yaws, axle, shots=None):
    """Share of a wheel's contact path that runs along its axle (sideways): 0 for a wheel on the axle the turn
    pivots about, growing with its distance from it (report-only until front-wheel steering exists)."""
    roll, side = _rolling(contact_pos, yaws, axle, shots)
    return side / (roll + side) if roll + side else 0.0
