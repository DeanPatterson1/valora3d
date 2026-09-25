"""Wheel angle from the subject's path: rolling without slip (TAXONOMY VD-02). The angular velocity of
a wheel rolling with velocity v on a ground with normal z is omega = (z x v) / r; its component along
the axle is the spin. The Blender wheel_roll block rotates each spinning island about its axle by
this angle (right-hand rule), so the contact point stays still on the ground."""
import math


def wheel_angles(pos, yaws, axle, radius):
    """Cumulative angle (radians) per frame. pos: subject positions per frame (world); yaws: the motion
    empty's yaw per frame (radians); axle: the wheel's axle in placed space."""
    out = [0.0]
    for i in range(1, len(pos)):
        dx, dy = pos[i][0] - pos[i - 1][0], pos[i][1] - pos[i - 1][1]
        c, s = math.cos(yaws[i]), math.sin(yaws[i])
        ax, ay = c * axle[0] - s * axle[1], s * axle[0] + c * axle[1]
        out.append(out[-1] + (-dy * ax + dx * ay) / radius)
    return out


def slip(angles, pos, radius):
    """|rolled distance - travelled distance| / travelled (0 = no slip). Straight paths only."""
    path = sum(math.dist(pos[i], pos[i - 1]) for i in range(1, len(pos)))
    return abs(abs(angles[-1] - angles[0]) * radius - path) / path if path else 0.0


def contact_points(pos, yaws, contact):
    """World contact-point track of one wheel: the motion empty's location + its yaw applied to the wheel's
    placed contact point (the wheel centre minus r straight down)."""
    out = []
    for (x, y, z), yw in zip(pos, yaws):
        c, s = math.cos(yw), math.sin(yw)
        out.append((x + c * contact[0] - s * contact[1], y + s * contact[0] + c * contact[1], z + contact[2]))
    return out


def wheel_angles_contact(contact_pos, yaws, axle, radius):
    """Curvature-aware wheel angles (hand-off H5): integrate each wheel's OWN contact-point path, so on an arc
    the outer wheel turns more than the inner one. contact_pos: this wheel's world contact point per frame."""
    return wheel_angles(contact_pos, yaws, axle, radius)


def _rolling(contact_pos, yaws, axle):
    """(rolling, lateral) metres of a contact path: each step split into the part across the axle (the wheel
    rolls it) and the part along it (scrub: an unsteered wheel pushed sideways on a turn)."""
    roll = side = 0.0
    for i in range(1, len(contact_pos)):
        dx, dy = contact_pos[i][0] - contact_pos[i - 1][0], contact_pos[i][1] - contact_pos[i - 1][1]
        c, s = math.cos(yaws[i]), math.sin(yaws[i])
        ax, ay = c * axle[0] - s * axle[1], s * axle[0] + c * axle[1]
        n = math.hypot(ax, ay) or 1.0
        roll += abs(-dy * ax / n + dx * ay / n)
        side += abs((dx * ax + dy * ay) / n)
    return roll, side


def slip_curved(angles, contact_pos, radius, yaws=None, axle=None):
    """|rolled - travelled| / travelled on this wheel's own contact path (0 = no slip), any path shape. With the
    yaws and the axle, travelled is the rolling part of the path (the part along the axle is scrub(), not
    slip: phase 5 does not steer the front wheels)."""
    if yaws is not None and axle is not None:
        path = _rolling(contact_pos, yaws, axle)[0]
    else:
        path = sum(math.hypot(contact_pos[i][0] - contact_pos[i - 1][0], contact_pos[i][1] - contact_pos[i - 1][1])
                   for i in range(1, len(contact_pos)))
    return abs(abs(angles[-1] - angles[0]) * radius - path) / path if path else 0.0


def scrub(contact_pos, yaws, axle):
    """Share of a wheel's contact path that runs along its axle (sideways): 0 for a wheel on the axle the turn
    pivots about, growing with its distance from it (report-only until front-wheel steering exists)."""
    roll, side = _rolling(contact_pos, yaws, axle)
    return side / (roll + side) if roll + side else 0.0
