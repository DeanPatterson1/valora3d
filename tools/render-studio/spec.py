"""RenderSpec: the one document a user controls (docs/superpowers/specs/2026-09-17-render-spec-design.md).

Pure Python, no bpy. Manifests in scenes/<id>.json declare what each scene
accepts; this module validates a spec against its manifest, produces the
default and random specs, and maps a spec onto rain_look.LOOK overrides.
"""
from copy import deepcopy
import json
import math
from pathlib import Path
import random
import zlib

SCHEMA = "modvision.render-spec/0"
SCENES_DIR = Path(__file__).resolve().parent / "scenes"
SEED_MAX = 2 ** 31 - 1
SOURCES = ("default", "random", "prompt")
PROMPT_MAX = 2000
GROUPS = ("world", "camera", "look", "lamps")


class SpecError(ValueError):
    pass


def _get(tree, path):
    node = tree
    for key in path.split("."):
        if not isinstance(node, dict) or key not in node:
            return None, False
        node = node[key]
    return node, True


def _set(tree, path, value):
    *parents, leaf = path.split(".")
    node = tree
    for key in parents:
        node = node.setdefault(key, {})
    node[leaf] = value


def load_manifest(scene_id):
    if not isinstance(scene_id, str) or not scene_id.isidentifier():
        raise SpecError("Unknown scene: " + repr(scene_id))
    path = SCENES_DIR / (scene_id + ".json")
    if not path.is_file():
        raise SpecError("Unknown scene: " + scene_id)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("id") != scene_id or manifest.get("schema") != SCHEMA:
        raise SpecError("Manifest for " + scene_id + " is inconsistent.")
    return manifest


def scene_ids():
    return sorted(path.stem for path in SCENES_DIR.glob("*.json"))


def default_spec(scene_id, seed=20260915):
    manifest = load_manifest(scene_id)
    document = deepcopy(manifest["default"])
    document.update({"schema": SCHEMA, "scene": scene_id, "seed": int(seed),
                     "provenance": {"source": "default"}})
    return validate_spec(document)


def _number(value, path):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise SpecError(path + " must be a finite number.")
    return value


def validate_spec(document):
    """Return a normalised copy or raise SpecError naming the offending field."""
    if not isinstance(document, dict):
        raise SpecError("RenderSpec must be a JSON object.")
    if document.get("schema") != SCHEMA:
        raise SpecError("schema must be " + SCHEMA)
    manifest = load_manifest(document.get("scene"))
    allowed = set(manifest["enums"]) | set(manifest["ranges"]) | set(manifest["booleans"])
    out = {"schema": SCHEMA, "scene": manifest["id"]}
    for group in GROUPS:
        values = document.get(group, {})
        if not isinstance(values, dict):
            raise SpecError(group + " must be an object.")
        for key in values:
            if group + "." + key not in allowed:
                raise SpecError("Unknown field " + group + "." + key)
    for path, options in manifest["enums"].items():
        value, present = _get(document, path)
        if not present or value not in options:
            raise SpecError(path + " must be one of " + ", ".join(options))
        _set(out, path, value)
    for path, (low, high) in manifest["ranges"].items():
        value, present = _get(document, path)
        if not present:
            raise SpecError(path + " is required.")
        _number(value, path)
        if not low <= value <= high:
            raise SpecError(path + " must be between " + str(low) + " and " + str(high))
        _set(out, path, value)
    for path in manifest["booleans"]:
        value, present = _get(document, path)
        if not present or not isinstance(value, bool):
            raise SpecError(path + " must be true or false.")
        _set(out, path, value)
    seed = document.get("seed", 20260915)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= SEED_MAX:
        raise SpecError("seed must be an integer between 0 and " + str(SEED_MAX))
    out["seed"] = seed
    provenance = document.get("provenance", {"source": "default"})
    if (not isinstance(provenance, dict) or set(provenance) - {"source", "prompt", "model", "sampler"}
            or provenance.get("source") not in SOURCES
            or any(not isinstance(provenance.get(k, ""), str) for k in ("prompt", "model", "sampler"))
            or len(provenance.get("prompt", "")) > PROMPT_MAX):
        raise SpecError("provenance must name a source of " + ", ".join(SOURCES))
    out["provenance"] = dict(provenance)
    unknown = set(document) - set(GROUPS) - {"schema", "scene", "seed", "provenance"}
    if unknown:
        raise SpecError("Unknown field " + ", ".join(sorted(unknown)))
    return out


def sample_spec(scene_id, seed):
    """Deterministic 'surprise me': one draw per manifest field, in manifest order."""
    manifest = load_manifest(scene_id)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= SEED_MAX:
        raise SpecError("seed must be an integer between 0 and " + str(SEED_MAX))
    # Strings hash differently per process (PYTHONHASHSEED), so the seed must be
    # an integer built from a stable digest, never a tuple containing str.
    rng = random.Random(zlib.crc32((scene_id + ":v0").encode()) * 1000003 + seed)
    sampling = manifest.get("sampling", {})
    document = {"schema": SCHEMA, "scene": scene_id, "seed": seed,
                "provenance": {"source": "random", "sampler": "v0"}}
    for path, options in manifest["enums"].items():
        weights = sampling.get(path)
        if isinstance(weights, dict):
            _set(document, path, rng.choices(options, [weights.get(o, 0) for o in options])[0])
        else:
            _set(document, path, rng.choice(options))
    for path, (low, high) in manifest["ranges"].items():
        window = sampling.get(path, [low, high])
        value = rng.uniform(max(low, window[0]), min(high, window[1]))
        _set(document, path, round(value, 4))
    for path in manifest["booleans"]:
        weight = sampling.get(path, 0.5)
        _set(document, path, rng.random() < weight)
    return validate_spec(document)


GRADES = {"agx-high-contrast": "AgX - High Contrast", "agx-base-contrast": "AgX - Base Contrast",
          "agx": "AgX", "filmic": "Filmic", "agx-medium-high-contrast": "AgX - Medium High Contrast"}
BASE = {"world_saturation": .85, "plate_saturation": .80, "foliage_saturation": .80,
        "haze_density": .0014, "fog_density": .0040, "drl_emission": 240.0, "tail_emission": 95.0}


def derive_seeds(seed):
    """Four decorrelated 31-bit seeds from one spec seed, one per scene random consumer.

    The Cycles sampling seed is LOOK['seed'] itself, set separately by spec_to_look."""
    rng = random.Random(int(seed) * 2654435761 % (2 ** 32))
    names = ("rain", "drips", "plants", "wind")
    values = []
    while len(set(values)) < len(names):
        values = [rng.randrange(1, SEED_MAX) for _ in names]
    return dict(zip(names, values))


def spec_to_look(document):
    """Translate a validated spec into rain_look.LOOK overrides. Only creative keys."""
    document = validate_spec(document)
    world, _camera, look, lamps = (document[g] for g in GROUPS)
    saturation = look["saturation"]
    out = {
        "falling_rain": world["weather"] == "raining",
        "wind": world["wind"],
        "exposure": look["exposure"],
        "view_look": GRADES[look["grade"]],
        "world_saturation": saturation,
        "plate_saturation": saturation * BASE["plate_saturation"] / BASE["world_saturation"],
        "foliage_saturation": saturation * BASE["foliage_saturation"] / BASE["world_saturation"],
        "haze_density": BASE["haze_density"] * look["fog"],
        "fog_density": BASE["fog_density"] * look["fog"],
        "bloom": look["bloom"],
        "halation": look["halation"],
        "veil": look["veil"],
        "drl_emission": BASE["drl_emission"] if lamps["drl"] else 0,
        "tail_emission": BASE["tail_emission"] if lamps["tail"] else 0,
        "seed": document["seed"],
        "scene_seed": document["seed"],
    }
    return out
