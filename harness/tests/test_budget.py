import pytest

from harness.budget import MAX_FRAMES_TOTAL, BudgetExceeded, RenderBudget


def test_budget_reserves_and_never_refunds():
    b = RenderBudget()
    assert MAX_FRAMES_TOTAL == 3 and b.reserve(2) == 2 and b.left == 1
    with pytest.raises(BudgetExceeded):
        b.reserve(2)
    assert b.used == 2                       # a refused reservation takes nothing


@pytest.mark.parametrize("n", [0, 4, -1])
def test_budget_total_is_capped(n):
    with pytest.raises(ValueError):
        RenderBudget(n)


@pytest.mark.parametrize("n", [float("nan"), float("inf"), 1.5, 1.0, True, "1", None])
def test_budget_total_must_be_a_whole_frame_count(n):
    with pytest.raises((ValueError, TypeError)):
        RenderBudget(n)


@pytest.mark.parametrize("n", [float("nan"), float("inf"), 0.5, 1.0, True, False, "1", None, 0, -1])
def test_reserve_rejects_non_frame_counts_and_leaves_usage_unchanged(n):
    b = RenderBudget()
    b.reserve(1)
    with pytest.raises((BudgetExceeded, ValueError, TypeError)):
        b.reserve(n)
    assert b.used == 1 and b.left == 2
    with pytest.raises(BudgetExceeded):
        b.reserve(3)                          # a poisoned 'used' (NaN) would let this through
    assert b.reserve(2) == 2 and b.left == 0
