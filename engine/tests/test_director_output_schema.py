import json

from engine.catalog import KINDS, Catalog
from engine.director.capabilities import BLOCK_ONLY_TAGS, KNOWN_TAGS
from engine.director.output_schema import (LIST_FIELDS, conforms, decompact, harness_only_tags,
                                           schema_problems, scene_output_schema)
from engine.director.rulebook import EXAMPLES_DIR


def test_schema_is_structurally_valid_for_structured_outputs():
    for compact in (False, True):
        s = scene_output_schema(Catalog.load(), compact=compact)
        assert schema_problems(s) == []


def test_schema_is_stable_and_has_no_pipeline_owned_fields_or_harness_blocks():
    a = json.dumps(scene_output_schema(Catalog.load()), sort_keys=True)
    assert a == json.dumps(scene_output_schema(Catalog.load()), sort_keys=True)
    props = scene_output_schema(Catalog.load())["properties"]
    assert not {"schema", "seed", "direction", "prompt", "format", "markers", "realism"} & set(props)
    assert '"turntable"' not in a and "camera.turntable" not in a


def test_unsupported_capability_offers_every_askable_tag():
    """Every vocabulary tag a user can ask for (it has phrases) plus "other" - including tags nothing
    delivers yet (field/sim kinds, weather). Block-only tags (camera.orbit...) and harness-only
    controls (camera.turntable) are never offered."""
    cat = Catalog.load()
    s = scene_output_schema(cat)
    enum = s["properties"]["unsupported"]["items"]["properties"]["capability"]["enum"]
    assert harness_only_tags(cat) == {"camera.turntable"}
    assert set(enum) == set(KNOWN_TAGS - BLOCK_ONLY_TAGS) | {"other"}
    assert len(enum) == len(set(enum)) and enum[-1] == "other"
    assert "weather.rain" in enum and "camera.turntable" not in enum and "camera.orbit" not in enum


def test_every_example_conforms():
    s = scene_output_schema(Catalog.load())
    for f in EXAMPLES_DIR.glob("*.json"):
        ex = json.loads(f.read_text(encoding="utf-8"))["script"]
        assert conforms(ex, s), f.stem


def test_conforms_rejects_extra_keys_and_unknown_ids():
    s = scene_output_schema(Catalog.load())
    ex = json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8"))["script"]
    assert not conforms({**ex, "bpy": "import os"}, s)
    assert not conforms({**ex, "world": {"id": "moon", "params": {}}}, s)


class _OnlyKinds:
    """A catalog view with some kinds emptied, as when a future kind (field, sim) has no blocks yet."""

    def __init__(self, cat, empty):
        self.cat, self.empty = cat, set(empty)

    def selectable_ids(self, kind):
        return [] if kind in self.empty else self.cat.selectable_ids(kind)

    def __getattr__(self, name):
        return getattr(self.cat, name)


def test_list_fields_extension_point_tolerates_kinds_without_blocks():
    assert set(LIST_FIELDS.values()) <= set(KINDS)
    for compact in (False, True):
        s = scene_output_schema(_OnlyKinds(Catalog.load(), {"effect"}), compact=compact)
        assert schema_problems(s) == [] and "effects" not in s["properties"]
        assert "effects" not in s["required"]


def test_decompact_turns_param_lists_back_into_objects():
    raw = {"world": {"id": "studio_cyc", "params": [{"name": "tone", "value": "black"}]},
           "shots": [{"camera": {"id": "arc_orbit", "params": [{"name": "sweepDeg", "value": 40}]}}],
           "effects": [{"id": "haze_volume", "params": []}]}
    out = decompact(raw)
    assert out["world"]["params"] == {"tone": "black"}
    assert out["shots"][0]["camera"]["params"] == {"sweepDeg": 40} and out["effects"][0]["params"] == {}


def test_rulebook_points_the_model_at_the_schema_tag_list_not_the_menu():
    from engine.director.rulebook import PREAMBLE
    flat = " ".join(PREAMBLE.split())
    assert "menu's vocabulary" not in flat  # the menu lists only what blocks do, never askable tags
    assert "capability tags the output format lists" in flat


def test_schema_complexity_is_counted_and_compact_stays_inside_the_limits():
    from engine.director.output_schema import COMPLEXITY_LIMITS, schema_complexity
    cat = Catalog.load()
    toy = {"type": "object", "additionalProperties": False, "required": ["a"],
           "properties": {"a": {"anyOf": [{"type": "number"}, {"type": "string"}]}, "b": {"type": "boolean"},
                          "c": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                           "required": [], "properties": {"d": {"enum": [1]}}}}}}
    assert schema_complexity(toy) == {"optional": 3, "unions": 1}
    full, compact = schema_complexity(scene_output_schema(cat)), schema_complexity(scene_output_schema(cat, compact=True))
    # 2026-09-25 catalog: full 69 optional / 4 unions, compact 4 / 8 (compact trades optional params
    # for one name/value union per block kind)
    assert compact["optional"] < full["optional"]
    assert all(compact[k] <= COMPLEXITY_LIMITS[k] for k in COMPLEXITY_LIMITS), (compact, COMPLEXITY_LIMITS)
