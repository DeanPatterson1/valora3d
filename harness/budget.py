"""Owner rule: at most 3 rendered frames per invocation on this PC. Frames are RESERVED before a render
starts and never refunded, so a crash mid-render cannot free budget for a retry loop."""
MAX_FRAMES_TOTAL = 3


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
