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
