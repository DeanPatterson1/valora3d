"""Contact with the ground (TAXONOMY CD-01, CD-07, CD-10; METHODS §2.1). Placed metres."""

# How far a subject settles into the ground, by ground type (eng; METHODS CD-07 "5-20 mm" into cover,
# CD-10 "5-10 mm" into rug pile). Hard floors: 0. Calibrate on golden renders of each world.
SINK_MM = {"studio": 0.0, "interior_floor": 0.0, "asphalt": 0.0, "water": 0.0, "rug": 7.0, "dirt": 5.0,
           "gravel": 8.0, "sand": 10.0, "grass": 12.0, "snow": 15.0}
MAX_SINK_FRAC = 0.1      # never sink more than 10% of the subject's height (a 5 cm lipstick on snow)
AO_DIST_FRAC = 0.05      # contact-occlusion reach, x subject height (eng; TAXONOMY CD-01 falloff 2-10%)
GROUND_TOL_M = 0.001     # a lowest point more than 1 mm above the ground is a visible gap


def sink_m(ground_type, subject_height):
    return min(SINK_MM[ground_type] / 1000.0, MAX_SINK_FRAC * subject_height)


def ao_distance(subject_height):
    return max(1e-4, AO_DIST_FRAC * subject_height)


GAP_TOL_FRAC = 0.005     # ... and at most 0.5% of the subject's height (1 mm floats a 5 cm lipstick; eng)


def gap_tol(height):
    return min(GROUND_TOL_M, GAP_TOL_FRAC * height)


RIDE_REACH = 1.5         # a vehicle's seam reaches 1.5 x its ride height, under the sills (eng; review fix 7)


def contact_reach(subject_height, ride_height=None):
    """Contact-occlusion reach: 5% of the height, or for a vehicle at least 1.5 x its ride height (5% of a
    1.3 m car is 65 mm, less than the gap under its body)."""
    return max(ao_distance(subject_height), RIDE_REACH * ride_height if ride_height else 0.0)


def grounded(min_z, sink, tol=GROUND_TOL_M):
    """The lowest evaluated point sits on the ground (or in it by at most the ground's sink)."""
    return -sink - tol <= min_z <= tol
