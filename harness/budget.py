"""Owner rule: at most 3 rendered frames per invocation on this PC. Frames are RESERVED before a render
starts and never refunded, so a crash mid-render cannot free budget for a retry loop.

Bakes (phase 6) get the same shape in minutes: a block's estimated bake seconds are reserved before
the bake starts and never refunded. MAX_BAKE_MIN is an engineering guess (calibration register)."""
import math

MAX_FRAMES_TOTAL = 3
MAX_BAKE_MIN = 90                             # (eng) estimated bake minutes per invocation


class BudgetExceeded(RuntimeError):
    pass


def _frames(n):
    """A frame count is a plain int (not a bool, float, NaN or string), so it can never poison 'used'."""
    if type(n) is not int:
        raise TypeError(f"frame count must be an int, got {n!r}")
    return n


class RenderBudget:
    def __init__(self, total=MAX_FRAMES_TOTAL):
        if not 0 < _frames(total) <= MAX_FRAMES_TOTAL:
            raise ValueError(f"render budget must be 1..{MAX_FRAMES_TOTAL} frames per invocation")
        self.total, self.used = total, 0

    def reserve(self, n=1):
        if _frames(n) < 1 or self.used + n > self.total:
            raise BudgetExceeded(f"{self.used}+{n} > {self.total} frames")
        self.used += n
        return n

    @property
    def left(self):
        return self.total - self.used


class BakeBudget:
    """Estimated bake seconds per invocation, reserved before each bake, never refunded. owner_ok lifts
    the cap (a heavy bake the owner approved) but every reservation still counts."""

    def __init__(self, max_min=MAX_BAKE_MIN, owner_ok=False):
        self.total_s, self.owner_ok, self.used_s = 60 * max_min, bool(owner_ok), 0

    def reserve_s(self, n):
        if isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) or n <= 0:
            raise ValueError(f"bake estimate must be a positive number of seconds, got {n!r}")
        if not self.owner_ok and self.used_s + n > self.total_s:
            raise BudgetExceeded(f"{self.used_s}+{n} s > {self.total_s} s of bake; heavy bakes need --owner-ok")
        self.used_s += n
        return n

    @property
    def left_s(self):
        return self.total_s - self.used_s
