"""Review chunk 6 (checker items #1, #3, #5)."""
from engine.checker import check
from engine.tests.camera_helpers import CAT, script_with
from engine.tests.test_director_package import _p


def _errors(r):
    return {i.code for i in r.issues if i.severity == "error"}


def test_a_reveal_opener_is_a_bad_hook():
    """#5: reveal_rise starts tight on a detail (framed_from > 0), so it cannot open, even when supplied directly."""
    s = script_with("reveal_rise", {}, index=0)
    s["shots"][0]["purpose"] = "hook"
    r = check(s, _p("sports_car"), CAT)
    assert "seq_bad_hook" in _errors(r)
