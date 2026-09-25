"""ReadOnceCatalog: memoised get() for read-only hot loops (craft_rules pose sampling, the dice's compatibility
pass). Same values as Catalog.get, one deep copy per manifest, everything else delegated."""
from engine.catalog import Catalog, ReadOnceCatalog


def test_same_values_one_copy_and_delegation(monkeypatch):
    cat = Catalog.load()
    calls = []
    real = cat.get
    monkeypatch.setattr(cat, "get", lambda k, b: calls.append((k, b)) or real(k, b))
    ro = ReadOnceCatalog(cat)
    assert ro.get("camera", "arc_orbit") == real("camera", "arc_orbit")
    for _ in range(50):
        ro.get("camera", "arc_orbit")
    assert calls == [("camera", "arc_orbit")]
    assert ro.selectable_ids("world") == cat.selectable_ids("world")
    assert ReadOnceCatalog(ro)._cat is cat                      # never nests


def test_the_craft_score_is_unchanged_by_the_memo():
    from engine.craft_rules import score_script
    from engine.director.fallback import build_fallback
    from engine.director.job import make_job
    from engine.tests.dice_seeds import phase4_catalog
    from engine.tests.test_director_package import _p
    cat, p = phase4_catalog(), _p("pocket_watch")
    s = build_fallback(make_job("", p, cat, seed=3, duration=10), p, cat)
    a = [(r.id, r.status, r.value) for r in score_script(s, p, cat)]
    b = [(r.id, r.status, r.value) for r in score_script(s, p, ReadOnceCatalog(cat))]
    assert a == b
