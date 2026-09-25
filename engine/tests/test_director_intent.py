import pytest

from engine.catalog import Catalog
from engine.director.direction import interim_direction
from engine.director.intent import format_notes, is_vague, make_format, read_pins
from engine.tests.test_director_package import _p


@pytest.mark.parametrize("prompt,pins", [
    ("", {}), ("make it look cool", {}),
    ("vertical 15 second ad", {"aspect": "9:16", "durationS": 15.0}),
    ("cinematic 16:9 commercial", {"aspect": "16:9"}),
    ("square post, 24fps", {"aspect": "1:1", "fps": 24}),
    ("for my instagram post", {"aspect": "4:5"}),
    ("a 60 s film", {"durationS": 60.0}),
])
def test_read_pins(prompt, pins):
    assert read_pins(prompt) == pins


def test_make_format_defaults_clamps_and_frame_aligns():
    f = make_format({}, seed=1)
    assert f == {"aspect": "9:16", "durationS": 10, "fps": 30}
    assert make_format({"durationS": 60.0}, 1)["durationS"] == 30
    f = make_format({"durationS": 7.33, "fps": 24}, 1)
    assert abs(f["durationS"] * 24 - round(f["durationS"] * 24)) < 1e-9


def test_format_notes():
    assert format_notes({}, {"aspect": "9:16", "durationS": 10, "fps": 30}) == ["no format given -> 9:16, 10 s"]
    assert format_notes({"durationS": 60.0}, {"aspect": "9:16", "durationS": 30, "fps": 30}) == [
        "no aspect given -> 9:16", "60 s is longer than the 30 s maximum -> 30 s"]


def test_is_vague():
    assert is_vague("") and is_vague("make it look cool") and is_vague("ad")
    assert not is_vague("a premium launch ad with a slow reveal from darkness")


def test_interim_direction_is_seeded_varied_and_family_aware():
    cat, watch, chair = Catalog.load(), _p("pocket_watch"), _p("mid_century_lounge_chair")
    assert interim_direction(5, watch, cat) == interim_direction(5, watch, cat)
    moods = {interim_direction(s, watch, cat).mood for s in range(30)}
    assert len(moods) >= 3 and "noir" not in moods
    assert {interim_direction(s, chair, cat).pace for s in range(30)} == {"calm"}
    d = interim_direction(5, watch, cat)
    assert d.source == "interim" and d.id == f"{d.mood}/{d.pace}/{d.tone}"
