import pytest

from engine.director.direction import AXES, Direction, direction_of, make_id, parse_id

AX = {"world": "studio_cyc", "mood": "teal_night", "tone": "black", "pace": "calm",
      "opener": "arc_orbit", "weather": "dry", "wind": "calm"}


def test_axes_order_is_fixed():
    assert AXES == ("world", "mood", "tone", "pace", "opener", "weather", "wind")


def test_id_round_trips():
    assert make_id(AX) == "studio_cyc/teal_night/black/calm/arc_orbit/dry/calm"
    assert parse_id(make_id(AX)) == AX


def test_legacy_three_part_id_parses_with_defaults():
    ax = parse_id("premium_dark/medium/black")
    assert ax == {"world": "studio_cyc", "mood": "premium_dark", "tone": "black", "pace": "medium",
                  "opener": "low_hero_push", "weather": "dry", "wind": "calm"}


@pytest.mark.parametrize("bad", ["", "a/b", "a/b/c/d", "a/b/c/d/e/f/g/h", "a//b", 7, None])
def test_bad_ids_raise(bad):
    with pytest.raises(ValueError):
        parse_id(bad)


def test_direction_of_fills_every_field_and_sorts_pins():
    d = direction_of(AX, "dice", pinned={"pace": "calm", "mood": "teal_night"})
    assert d.id == make_id(AX) and d.source == "dice" and d.pinned == ("mood", "pace")
    assert d.axes() == AX and (d.mood, d.pace, d.tone, d.opener, d.world) == ("teal_night", "calm", "black",
                                                                              "arc_orbit", "studio_cyc")


def test_old_constructor_still_works():
    d = Direction("premium_dark/medium/black", "premium_dark", "medium", "black")
    assert d.source == "interim" and d.opener == "low_hero_push" and d.world == "studio_cyc"


def test_from_script_is_a_replay():
    d = Direction.from_script({"direction": {"id": make_id(AX), "source": "dice"}})
    assert d.axes() == AX and d.source == "replay"
