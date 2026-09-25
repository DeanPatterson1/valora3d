"""Review chunk5 #1: the settle hold and the rate cap are revalidated after every repair (a toss slowed by the
rate cap after the settle rule placed its landing must still land 0.8 s before the end), and a combination
that cannot satisfy both is an error."""
from engine.motion_rules import SETTLE_BEFORE_END_S, apply_motion_rules, peak_rate_deg_s
from engine.tests.motion_helpers import CAT, defaults, module, script
from engine.tests.test_director_package import _p

TOSS = module("toss_tumble")
CAP = CAT.get("motion", "toss_tumble")["rateCap"]["degS"]


def _run(prm, duration):
    s = script("toss_tumble", {**defaults("toss_tumble"), **prm}, duration=duration)
    issues = []
    apply_motion_rules(s, CAT, _p("sneaker"), issues)     # the rules alone: the clip is shorter than the shots
    full = {**defaults("toss_tumble"), **s["subject"]["motion"]["params"]}
    return full, issues


def _rate(full, duration):
    p = _p("sneaker")
    t0, t1 = TOSS.window(full, p, duration)
    return peak_rate_deg_s(lambda t: TOSS.sample(full, p, t, duration), max(0.0, t0), min(duration, t1))


def test_a_toss_slowed_by_the_rate_cap_still_lands_before_the_hold():
    # the settle rule moves startS so the fast toss lands at 3.2 s; the cap then slows it to ~1 s of air
    full, issues = _run({"spins": 3, "timeScale": 1.0, "startS": 6.0}, 4)
    codes = {i.code for i in issues}
    assert not [i for i in issues if i.severity == "error"], [(i.code, i.message) for i in issues]
    assert {"motion_ends_unsettled", "spin_rate_cap"} <= codes
    assert TOSS.rest_s(full, _p("sneaker"), 4.0) <= 4.0 - SETTLE_BEFORE_END_S + 1e-6
    assert _rate(full, 4.0) <= CAP + 1e-6


def test_a_toss_that_cannot_hold_and_keep_under_the_cap_is_an_error():
    # 0.7 s to land in, but the cap needs about 1 s of air: the two rules can only undo each other
    full, issues = _run({"spins": 1, "timeScale": 1.0, "startS": 0.5}, 1.5)
    errs = [i for i in issues if i.severity == "error"]
    assert [i.code for i in errs] == ["motion_too_long"], [(i.code, i.message) for i in issues]
    assert "cap" in errs[0].message
