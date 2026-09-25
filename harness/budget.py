"""Owner rule: at most 3 rendered frames per invocation on this PC. Frames are RESERVED before a render
starts and never refunded, so a crash mid-render cannot free budget for a retry loop."""
MAX_FRAMES_TOTAL = 3


class BudgetExceeded(RuntimeError):
    pass


class RenderBudget:
    def __init__(self, total=MAX_FRAMES_TOTAL):
        if not 0 < total <= MAX_FRAMES_TOTAL:
            raise ValueError(f"render budget must be 1..{MAX_FRAMES_TOTAL} frames per invocation")
        self.total, self.used = total, 0

    def reserve(self, n=1):
        if n < 1 or self.used + n > self.total:
            raise BudgetExceeded(f"{self.used}+{n} > {self.total} frames")
        self.used += n
        return n

    @property
    def left(self):
        return self.total - self.used
