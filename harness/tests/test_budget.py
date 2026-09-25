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
