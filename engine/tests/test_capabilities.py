import pytest

from engine.catalog import KINDS, Catalog
from engine.director.capabilities import BLOCK_ONLY_TAGS, KNOWN_TAGS, detect, merge_llm, unsupported
from engine.tests.test_director_package import _p


@pytest.mark.parametrize("text,tags", [
    ("add rain", {"weather.rain"}),
    # research/physics/BLOCKS.md §4.1: the generic tag stays, and the fine tag is reported too
    ("liquid running down the can", {"sim.liquid", "liquid.run_down"}),
    ("make the car drive", {"motion.drive"}),
    ("character walks", {"motion.character_clip"}),
    ("rainy night", {"weather.rain", "grade.night"}),
    ("sunset on the beach with music", {"lighting.sun", "grade.warm", "world.nature", "audio.music"}),
    ("", set()), ("make it look cool", set()),
    ("shallow depth of field", set()), ("hard drive product shot", set()),
    ("park it in the studio", {"world.studio"}), ("without any rain or snow", set()),
])
def test_detect(text, tags):
    assert {a["capability"] for a in detect(text)} == tags


def test_negation_is_not_an_ask():
    assert detect("no text, no music, without rain") == []


def test_unsupported_notes_and_supported_asks_are_not_reported():
    cat, prof = Catalog.load(), _p("pocket_watch")
    got = unsupported(detect("rainy night with neon"), cat, prof)
    assert [u["capability"] for u in got] == ["weather.rain", "lighting.neon"]  # grade.night is supported
    assert got[0]["note"] == "Rain isn't available yet, so the video is dry."
    assert got[0]["source"] == "prompt" and got[0]["ask"].lower().startswith("rain")


def test_marker_asks_carry_their_marker_id():
    cat, prof = Catalog.load(), _p("pocket_watch")
    asks = detect("water dripping here", source="marker:m1")
    assert unsupported(asks, cat, prof)[0]["source"] == "marker:m1"


def test_llm_additions_merge_after_detections_without_duplicates():
    cat, prof = Catalog.load(), _p("pocket_watch")
    det = unsupported(detect("add rain"), cat, prof)
    llm = [{"ask": "rain", "capability": "weather.rain"}, {"ask": "hologram shimmer", "capability": "other"},
           {"ask": "studio look", "capability": "world.studio"}]  # supported: dropped
    got = merge_llm(det, llm, cat, prof)
    assert [u["capability"] for u in got] == ["weather.rain", "other"]
    assert got[1]["note"] == "Something you asked for isn't available yet, so it was left out."
    assert got[1]["source"] == "director"


def test_every_block_tag_is_known_and_every_ask_has_a_note():
    cat = Catalog.load()
    for kind in KINDS:
        for bid in cat.ids(kind):
            assert set(cat.get(kind, bid).get("capabilities", [])) <= KNOWN_TAGS, bid
    assert BLOCK_ONLY_TAGS <= KNOWN_TAGS


def test_vocabulary_is_well_formed():
    import re
    from engine.director.capabilities import VOCAB
    for tag, v in VOCAB.items():
        assert re.fullmatch(r"[a-z_]+\.[a-z_]+", tag), tag
        assert not v["phrases"] or v["note"], f"{tag}: an askable tag needs a user note"
        for ph in v["phrases"]:
            re.compile(ph)


@pytest.mark.parametrize("text,tag", [("leaves blowing in the wind", "sim.debris_wind"),
                                      ("a tumbleweed rolls across", "sim.debris_wind"),
                                      ("ball bouncing", "sim.rolling")])
def test_physics_asks_are_detected(text, tag):
    assert tag in {a["capability"] for a in detect(text)}


def test_physics_vocabulary_from_blocks_md_is_present():
    # research/physics/BLOCKS.md §4.2: every published tag has a vocabulary entry
    for tag in ("wind.breeze", "wind.strong", "surface.wet", "liquid.condensation", "liquid.pour",
                "particles.leaves", "rigid.tumbleweed", "cloth.drape_reveal", "smoke.plume",
                "fire.flames", "vehicle.tyre_smoke", "motion.float", "contact.tyre", "contact.ground",
                "vehicle.suspension", "foliage.sway"):
        assert tag in KNOWN_TAGS, tag
    assert {"contact.tyre", "contact.ground", "foliage.sway"} <= BLOCK_ONLY_TAGS


@pytest.mark.parametrize("text,tag,present", [
    ("windy day", "wind.breeze", True), ("windy day", "sim.debris_wind", False),
    ("rolling fog", "motion.roll", False),            # BLOCKS.md §4 phrase collisions
    ("a tumbleweed rolls across", "rigid.tumbleweed", True),
    ("ice-cold drink", "liquid.condensation", True), ("burnout", "vehicle.tyre_smoke", True),
    ("the can drips with condensation", "liquid.condensation", True),
])
def test_physics_phrase_collisions(text, tag, present):
    assert (tag in {a["capability"] for a in detect(text)}) is present
