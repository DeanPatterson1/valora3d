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


# --- review fixes 2026-09-24 (phase 3 chunks 0-1) ---

@pytest.mark.parametrize("text,tags", [
    ("no text, just music", {"audio.music"}),
    ("no logo and heavy rain", {"weather.rain"}),
    ("no people, fog please", {"atmosphere.fog"}),
    ("not only rain but snow", {"weather.rain", "weather.snow"}),
    ("no rain. add smoke", {"smoke.plume"}),
    ("without rain; with snow", {"weather.snow"}),
])
def test_negation_stops_at_the_clause(text, tags):
    assert tags <= {a["capability"] for a in detect(text)}


@pytest.mark.parametrize("text", ["rain-free", "rain free", "no-rain", "don’t add rain", "don't add rain",
                                  "avoid smoke", "with zero smoke", "less rain", "never any rain"])
def test_negation_words(text):
    assert detect(text) == []


@pytest.mark.parametrize("text,tag", [
    ("it rains hard", "weather.rain"), ("storms roll in", "weather.rain"), ("it snows", "weather.snow"),
    ("two sunsets", "lighting.sun"), ("explosions everywhere", "fire.explosion"),
    ("the tank exploded", "fire.explosion"), ("the car drove off", "motion.drive"),
    ("the robot walked in", "motion.character_clip"), ("honey poured over it", "liquid.pour"),
    ("fireworks behind the car", "fire.fireworks"), ("a lightning strike", "weather.lightning"),
    ("add motion blur", "camera.motion_blur"),
])
def test_inflections_and_new_tags(text, tag):
    assert tag in {a["capability"] for a in detect(text)}


@pytest.mark.parametrize("text,tag", [
    ("water-resistant watch", "sim.liquid"), ("front-wheel drive hatchback", "motion.drive"),
    ("all wheel drive", "motion.drive"), ("fire-red paint", "fire.flames"),
    ("dark blue car", "grade.night"), ("under the pouring rain", "liquid.pour"),
    ("lighting from the left", "weather.lightning"), ("fundamentals", "grade.vivid"),
])
def test_known_false_positives(text, tag):
    assert tag not in {a["capability"] for a in detect(text)}


def test_pouring_rain_is_rain():
    assert "weather.rain" in {a["capability"] for a in detect("under the pouring rain")}


def test_new_tags_are_unsupported_until_a_block_provides_them():
    cat, prof = Catalog.load(), _p("sports_car")
    got = {u["capability"] for u in unsupported(detect("fireworks, lightning and motion blur"), cat, prof)}
    assert {"fire.fireworks", "weather.lightning", "camera.motion_blur"} <= got


def test_one_note_per_phrase():
    cat, prof = Catalog.load(), _p("sports_car")
    got = unsupported(detect("an explosion"), cat, prof)
    assert len(got) == 1 and got[0]["ask"].lower() == "explosion"


NINETEEN = ("rain, snow, fog, smoke, fire, sparks, confetti, glitter, petals, bubbles, music, text, "
            "neon, sunset, drone, handheld, driving on a street, underwater")


def test_overflow_is_merged_and_the_checker_accepts_it():
    import json
    from pathlib import Path
    from engine.script import MAX_UNSUPPORTED, validate_and_repair
    cat, prof = Catalog.load(), _p("sports_car")
    asks = detect(NINETEEN)
    raw = []
    for a in asks:  # what unsupported() sees before the cap
        if a["capability"] not in cat.capabilities(prof) and a["ask"].lower() not in {r.lower() for r in raw}:
            raw.append(a["ask"])
    assert len(raw) > MAX_UNSUPPORTED
    got = unsupported(asks, cat, prof)
    assert len(got) == MAX_UNSUPPORTED
    assert got[-1]["ask"] == f"…and {len(raw) - MAX_UNSUPPORTED + 1} more things"
    assert got[-1]["capability"] == "other"
    s = json.loads((Path(__file__).parent / "fixtures" / "script_valid.json").read_text())
    s["unsupported"] = got
    assert not [i for i in validate_and_repair(s, cat)[1] if i.code == "bad_unsupported"]


def test_capabilities_count_only_blocks_the_director_can_reach():
    from engine.catalog import _always_on
    from engine.director.menu import KIND_ORDER
    cat = Catalog.load()
    want = set()
    for kind in KINDS:
        for bid in cat.ids(kind):
            m = cat.get(kind, bid)
            if _always_on(kind, m) or (kind in KIND_ORDER and bid in cat.selectable_ids(kind)):
                want |= set(m.get("capabilities", []))
    assert cat.capabilities(None) == want


def test_every_kind_with_selectable_blocks_is_on_the_menu():
    from engine.director.menu import KIND_ORDER
    cat = Catalog.load()
    missing = [k for k in KINDS if cat.selectable_ids(k) and k not in KIND_ORDER]
    assert missing == [], f"selectable blocks of kind {missing} have no menu slot (menu.KIND_ORDER)"


def test_capabilities_ignore_a_selectable_block_of_an_off_menu_kind(tmp_path):
    import json
    import shutil
    from engine.catalog import BLOCKS_DIR
    root = tmp_path / "blocks"
    shutil.copytree(BLOCKS_DIR, root)
    src = next((root / "world").iterdir())
    dst = root / "sim" / "fake_rain"
    dst.parent.mkdir(exist_ok=True)
    shutil.copytree(src, dst)
    m = json.loads((dst / "block.json").read_text(encoding="utf-8"))
    m.update(id="fake_rain", kind="sim", capabilities=["weather.rain"], directorSelectable=True)
    m.pop("alwaysOn", None)
    (dst / "block.json").write_text(json.dumps(m), encoding="utf-8")
    cat = Catalog.load(root)
    assert "fake_rain" in cat.selectable_ids("sim")
    assert "weather.rain" not in cat.capabilities(None)
