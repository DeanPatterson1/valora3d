# tools/render-studio/test_spec.py
import copy
from pathlib import Path
import sys
import types
import unittest

import spec

# rain_look.py imports bpy at module scope, so outside Blender the LOOK dict is
# only reachable behind a stub. The mapping tests read LOOK's values (a plain
# literal); nothing here touches Blender itself.
for _name in ("bpy", "bpy.types", "bpy.props", "bpy.utils", "mathutils"):
    sys.modules.setdefault(_name, types.ModuleType(_name))


class _Stub:
    def __init__(self, *args, **kwargs):
        pass


for _name in ("Vector", "Matrix", "Euler", "Quaternion", "Color"):
    if not hasattr(sys.modules["mathutils"], _name):
        setattr(sys.modules["mathutils"], _name, _Stub)


class ManifestTests(unittest.TestCase):
    def test_every_scene_has_a_manifest_whose_default_validates(self):
        for scene_id in ("rainy_courtyard", "turntable", "night_garage"):
            manifest = spec.load_manifest(scene_id)
            self.assertEqual(manifest["id"], scene_id)
            default = spec.default_spec(scene_id)
            self.assertEqual(default["scene"], scene_id)
            self.assertEqual(spec.validate_spec(default), default)

    def test_unknown_scene_is_rejected(self):
        with self.assertRaises(spec.SpecError):
            spec.load_manifest("beach")
        with self.assertRaises(spec.SpecError):
            spec.validate_spec({"schema": spec.SCHEMA, "scene": "beach"})


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.good = spec.default_spec("rainy_courtyard")

    def bad(self, path, value):
        broken = copy.deepcopy(self.good)
        target = broken
        *parents, leaf = path.split(".")
        for key in parents:
            target = target[key]
        target[leaf] = value
        return broken

    def test_enum_range_boolean_and_unknown_key_errors_name_the_field(self):
        cases = [
            ("world.weather", "snow", "world.weather"),
            ("look.exposure", 5, "look.exposure"),
            ("look.exposure", "dark", "look.exposure"),
            ("look.exposure", float("nan"), "look.exposure"),
            ("lamps.drl", "yes", "lamps.drl"),
            ("seed", -1, "seed"),
            ("seed", 2 ** 40, "seed"),
        ]
        for path, value, expected in cases:
            with self.assertRaises(spec.SpecError) as caught:
                spec.validate_spec(self.bad(path, value))
            self.assertIn(expected, str(caught.exception))
        extra = copy.deepcopy(self.good)
        extra["look"]["shutter"] = 1
        with self.assertRaises(spec.SpecError) as caught:
            spec.validate_spec(extra)
        self.assertIn("look.shutter", str(caught.exception))
        extra = copy.deepcopy(self.good)
        extra["camera_path"] = []
        with self.assertRaises(spec.SpecError):
            spec.validate_spec(extra)

    def test_schema_string_is_required(self):
        broken = copy.deepcopy(self.good)
        broken["schema"] = "modvision.render-spec/9"
        with self.assertRaises(spec.SpecError):
            spec.validate_spec(broken)

    def test_provenance_is_optional_bounded_and_preserved(self):
        with_source = copy.deepcopy(self.good)
        with_source["provenance"] = {"source": "prompt", "prompt": "dusk drizzle", "model": "x"}
        self.assertEqual(spec.validate_spec(with_source)["provenance"]["source"], "prompt")
        with_source["provenance"]["prompt"] = "x" * 2001
        with self.assertRaises(spec.SpecError):
            spec.validate_spec(with_source)
        with_source["provenance"] = {"source": "telepathy"}
        with self.assertRaises(spec.SpecError):
            spec.validate_spec(with_source)

    def test_integers_are_accepted_where_floats_are_expected_but_bools_are_not(self):
        ok = self.bad("look.exposure", 0)
        self.assertEqual(spec.validate_spec(ok)["look"]["exposure"], 0)
        with self.assertRaises(spec.SpecError):
            spec.validate_spec(self.bad("look.exposure", True))


class SamplingTests(unittest.TestCase):
    def test_same_seed_same_spec_and_different_seeds_differ(self):
        a = spec.sample_spec("rainy_courtyard", 7)
        b = spec.sample_spec("rainy_courtyard", 7)
        c = spec.sample_spec("rainy_courtyard", 8)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(a["seed"], 7)
        self.assertEqual(a["provenance"], {"source": "random", "sampler": "v0"})

    def test_samples_validate_and_stay_inside_sampling_windows(self):
        manifest = spec.load_manifest("rainy_courtyard")
        low, high = manifest["sampling"]["look.exposure"]
        for seed in range(200):
            document = spec.sample_spec("rainy_courtyard", seed)
            self.assertEqual(spec.validate_spec(document), document)
            self.assertTrue(low <= document["look"]["exposure"] <= high)

    def test_weighted_enums_follow_their_weights_roughly(self):
        draws = [spec.sample_spec("rainy_courtyard", seed)["world"]["weather"] for seed in range(400)]
        raining = draws.count("raining") / len(draws)
        self.assertTrue(0.5 < raining < 0.7, raining)

    def test_sampler_is_pinned(self):
        # A fixed literal guards against silently changing the draw order or the
        # seeding, which would change every user's "same again" render. Fill the
        # literal ONCE from the first green run (print it), then never touch it.
        document = spec.sample_spec("turntable", 1)
        self.assertEqual(document["seed"], 1)
        self.assertEqual((document["look"]["grade"], document["look"]["exposure"]),
                         PINNED_TURNTABLE_SEED_1)


PINNED_TURNTABLE_SEED_1 = ("agx-medium-high-contrast", -0.1523)   # pinned from the first green run; never touch it


class LookMappingTests(unittest.TestCase):
    def test_default_courtyard_spec_maps_to_look_defaults(self):
        import rain_look
        look = spec.spec_to_look(spec.default_spec("rainy_courtyard"))
        for key in ("exposure", "view_look", "world_saturation", "falling_rain", "wind", "drl_emission", "tail_emission", "seed"):
            self.assertEqual(look[key], rain_look.LOOK[key], key)
        self.assertEqual(look["scene_seed"], 20260915)
        self.assertNotIn("probe_camera", look)
        self.assertNotIn("adaptive_threshold", look)

    def test_weather_grade_lamps_fog_map(self):
        document = spec.default_spec("rainy_courtyard")
        document["world"]["weather"] = "after-rain"
        document["look"]["grade"] = "filmic"
        document["look"]["fog"] = 2.0
        document["look"]["saturation"] = 0.5
        document["lamps"]["drl"] = False
        document["seed"] = 42
        look = spec.spec_to_look(spec.validate_spec(document))
        self.assertIs(look["falling_rain"], False)
        self.assertEqual(look["view_look"], "Filmic")
        self.assertAlmostEqual(look["fog_density"], 0.0040 * 2.0)
        self.assertAlmostEqual(look["haze_density"], 0.0014 * 2.0)
        self.assertAlmostEqual(look["world_saturation"], 0.5)
        self.assertAlmostEqual(look["plate_saturation"], 0.5 * (0.80 / 0.85))
        self.assertEqual(look["drl_emission"], 0)
        self.assertNotIn("freeze_camera", look)
        self.assertEqual((look["seed"], look["scene_seed"]), (42, 42))

    def test_every_emitted_key_exists_in_look(self):
        import rain_look
        for scene_id in spec.scene_ids():
            for seed in (0, 3):
                look = spec.spec_to_look(spec.sample_spec(scene_id, seed))
                self.assertFalse(set(look) - set(rain_look.LOOK), set(look) - set(rain_look.LOOK))

    def test_derived_seeds_are_distinct_and_stable(self):
        seeds = spec.derive_seeds(42)
        self.assertEqual(set(seeds), {"rain", "drips", "plants", "wind"})
        self.assertEqual(len(set(seeds.values())), 4)
        self.assertEqual(seeds, spec.derive_seeds(42))
        self.assertNotEqual(seeds, spec.derive_seeds(43))

    def test_legacy_default_seed_is_pinned_by_the_snapshot_script(self):
        text = (Path(__file__).with_name('render_snapshot.py')).read_text(encoding='utf-8')
        self.assertIn("'rain': 20260916, 'drips': 20260920, 'plants': 20260919, 'wind': 20260917", text)


if __name__ == "__main__":
    unittest.main()
