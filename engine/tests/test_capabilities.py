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
    # phase 5 (Task 88): rain and neon are delivered now; smoke and fireworks are not
    got = unsupported(detect("smoky night with fireworks"), cat, prof)
    assert [u["capability"] for u in got] == ["smoke.plume", "fire.fireworks"]  # grade.night is supported
    assert got[0]["note"] == "Smoke isn't available yet, so it was left out."
    assert got[0]["source"] == "prompt" and got[0]["ask"].lower().startswith("smok")


def test_marker_asks_carry_their_marker_id():
    cat, prof = Catalog.load(), _p("pocket_watch")
    asks = detect("water dripping here", source="marker:m1")
    assert unsupported(asks, cat, prof)[0]["source"] == "marker:m1"


def test_llm_additions_merge_after_detections_without_duplicates():
    cat, prof = Catalog.load(), _p("pocket_watch")
    det = unsupported(detect("add smoke"), cat, prof)
    llm = [{"ask": "smoke", "capability": "smoke.plume"}, {"ask": "hologram shimmer", "capability": "other"},
           {"ask": "studio look", "capability": "world.studio"}]  # supported: dropped
    got = merge_llm(det, llm, cat, prof)
    assert [u["capability"] for u in got] == ["smoke.plume", "other"]
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


NINETEEN = ("smoke, fire, sparks, confetti, glitter, petals, bubbles, music, text, drone, underwater, "
            "lightning, fireworks, embers, steam, flags, tumbleweeds, confetti cannon")   # none delivered (phase 5)


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
    m.update(id="fake_rain", kind="sim", capabilities=["smoke.plume"], directorSelectable=True)   # phase 5: a tag
    m.pop("alwaysOn", None)                                                                         # nothing delivers
    (dst / "block.json").write_text(json.dumps(m), encoding="utf-8")
    cat = Catalog.load(root)
    assert "fake_rain" in cat.selectable_ids("sim")
    assert "smoke.plume" not in cat.capabilities(None)


def test_character_walks_is_supported_only_for_animated_models():
    cat = Catalog.load()
    assert unsupported(detect("character walks"), cat, _p("cesium_man")) == []
    got = unsupported(detect("character walks"), cat, _p("pocket_watch"))
    assert got[0]["note"] == "This model has no animation of its own, so it is shown still."


def test_play_clip_ref_picks_the_clip_the_ask_names():
    import dataclasses
    from engine.director.capabilities import clip_line, play_clip_ref
    man = _p("cesium_man")
    two = dataclasses.replace(man, animationClips=[
        {**man.animationClips[0], "index": 0, "nameHint": "Idle"},
        {**man.animationClips[0], "index": 1, "nameHint": "Walk", "seamless": False}])
    assert play_clip_ref(detect("character walks"), two) == {"id": "play_clip", "params": {"clip": 1}}
    assert play_clip_ref(detect("character walks"), man) == {"id": "play_clip", "params": {"clip": 0}}  # Anim_0
    assert "clip 1" in clip_line(two, 1) and "backwards" in clip_line(two, 1)
    assert "clip 0" in clip_line(man, 0) and "backwards" in clip_line(man, 0)   # measured: not seamless
    assert "looped" in clip_line(dataclasses.replace(man, animationClips=[{**man.animationClips[0], "seamless": True}]), 0)
    walk = dataclasses.replace(man, animationClips=[{**man.animationClips[0], "seamless": True, "rootMotion": True}])
    assert "plays in place" in clip_line(walk, 0) and "plays in place" not in clip_line(man, 0)


def test_a_model_with_clips_from_an_old_clip_map_cannot_play_them():
    # independent review P1: never a silent wrong action; the ask is reported with a re-ingest note
    import dataclasses
    cat = Catalog.load()
    man = _p("cesium_man")
    old = dataclasses.replace(man, animationClips=[{k: v for k, v in man.animationClips[0].items()
                                                    if k != "clipMapVersion"}])
    assert "motion.character_clip" in cat.capabilities(man)
    assert "motion.character_clip" not in cat.capabilities(old)
    got = unsupported(detect("character walks"), cat, old)
    assert got and "re-ingest" in got[0]["note"]


def test_character_clip_note_is_vocabulary_data():
    from engine.director.capabilities import NOTES
    assert NOTES["motion.character_clip"] == "This model has no animation of its own, so it is shown still."


# --- phase 5 (Task 85): vocabulary, phrase collisions, world-blocked and partial-support notes ------------

import pytest  # noqa: E402

from engine.director.capabilities import finish_unsupported, world_blocked  # noqa: E402


def _grown(cat=None):
    """The catalog with every growth block selectable (Task 88 flips them on disk; until then in memory)."""
    import json as _json
    from pathlib import Path as _Path
    cat = cat or Catalog.load()
    growth = _json.loads((_Path(__file__).resolve().parents[1] / "catalog_growth.json").read_text(encoding="utf-8"))
    for ref in growth["blocks"]:
        cat._blocks[tuple(ref.split("/"))]["directorSelectable"] = True
    return cat


@pytest.mark.parametrize("text,tag", [
    ("light drizzle", "weather.rain"), ("a downpour", "weather.rain"), ("pouring rain", "weather.rain"),
    ("after the rain", "surface.wet"), ("puddles", "surface.wet"), ("misty morning", "atmosphere.fog"),
    ("hazy morning", "atmosphere.fog"), ("snowy", "weather.snow"), ("wintery scene", "weather.snow"),
    ("slides in", "motion.slide"), ("rising crane reveal", "camera.crane"), ("dutch angle", "camera.dutch"),
    ("tracking shot", "camera.tracking"), ("side profile slide", "camera.slide"),
    ("spin it on a pedestal", "motion.spin"), ("golden hour", "world.nature"), ("a wheat meadow", "world.nature"),
    ("neon street", "world.street"), ("downtown", "world.street"), ("macro slide", "camera.macro"),
    ("drops and bounces", "motion.drop"), ("a burnout", "motion.drive")])
def test_new_phrases_detect(text, tag):
    assert tag in {a["capability"] for a in detect(text)}


@pytest.mark.parametrize("text,not_tag", [("rolling fog", "motion.roll"), ("falling leaves", "motion.drop"),
                                          ("falling petals", "motion.drop"), ("snow white backdrop", "weather.snow"),
                                          ("rain-free", "weather.rain"), ("drops and bounces", "sim.rolling")])
def test_phrase_collisions(text, not_tag):
    assert not_tag not in {a["capability"] for a in detect(text)}


STUDIO = {"world": {"id": "studio_cyc"}, "effects": [], "subject": {"placement": "ground", "motion": {"id": "static"}},
          "shots": []}


def test_rain_is_delivered_outdoors_and_honest_in_the_studio():
    cat, p = _grown(), _p("sports_car")
    asks = detect("rain")
    assert unsupported(asks, cat, p) == []                                # some world can host it
    out = unsupported(asks, cat, p, script=STUDIO)
    assert out and "outdoor" in out[0]["note"].lower() and out[0]["capability"] == "weather.rain"
    street = {**STUDIO, "world": {"id": "night_street"}}
    assert unsupported(asks, cat, p, script=street) == []


@pytest.mark.parametrize("prompt,tag", [("snowy", "weather.snow"), ("after the rain", "surface.wet"),
                                        ("driving fast", "motion.drive"), ("golden hour sun", "lighting.sun")])
def test_world_blocked_asks_say_what_the_studio_does(prompt, tag):
    cat, p = _grown(), _p("sports_car")
    out = unsupported(detect(prompt), cat, p, script=STUDIO)
    assert tag in [u["capability"] for u in out]
    assert all("isn't available yet" not in u["note"] for u in out)   # it exists; the studio blocks it


def test_fog_is_not_world_blocked_in_the_studio():
    """ground_fog needs only a ground (the studio has one): the ask is delivered, not blocked."""
    assert unsupported(detect("foggy"), _grown(), _p("sports_car"), script=STUDIO) == []


def test_tracking_needs_a_moving_subject():
    cat, p = _grown(), _p("pocket_watch")
    out = unsupported(detect("tracking shot"), cat, p, script={**STUDIO, "world": {"id": "night_street"}})
    assert out and "move" in out[0]["note"]
    drive = {**STUDIO, "world": {"id": "night_street"}, "subject": {"placement": "ground", "motion": {"id": "drive"}}}
    assert world_blocked("camera.tracking", drive, cat, _p("sports_car")) is None


def test_partial_support_notes_follow_the_script():
    cat, p = _grown(), _p("pocket_watch")
    asks = detect("water running down it")
    dry = finish_unsupported({**STUDIO, "unsupported": unsupported(asks, cat, p)}, asks, cat, p)
    wet = finish_unsupported({**STUDIO, "effects": [{"id": "droplets"}], "unsupported": unsupported(asks, cat, p)},
                             asks, cat, p)
    run = lambda s: next(u["note"] for u in s["unsupported"] if u["capability"] == "liquid.run_down")  # noqa: E731
    assert "droplets instead" not in run(dry) and "droplets instead" in run(wet)
    spray = unsupported(detect("road spray"), cat, _p("sports_car"))
    assert spray[0]["note"] == "Road spray isn't available yet; the car drives through the wet without spray."


def test_finish_adds_a_world_blocked_ask_the_script_dropped():
    """A deliverable ask the final script does not deliver because of its world is reported, never silent."""
    cat, p = _grown(), _p("sports_car")
    asks = detect("rain")
    s = finish_unsupported({**STUDIO, "assumptions": []}, asks, cat, p)
    assert [u["capability"] for u in s["unsupported"]] == ["weather.rain"]
    assert s["unsupported"][0]["note"] in s["assumptions"]
    rainy = {**STUDIO, "world": {"id": "night_street"}, "effects": [{"id": "rain"}], "assumptions": []}
    assert "unsupported" not in finish_unsupported(rainy, asks, cat, p)


def test_a_roll_is_reported_by_its_own_tag():
    """'rolls across' is motion.roll (a real block since phase 5), never the coarse sim.rolling line."""
    tags = [a["capability"] for a in detect("the can rolls across the table")]
    assert "motion.roll" in tags and "sim.rolling" not in tags
