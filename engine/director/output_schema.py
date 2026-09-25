"""The JSON schema the model's reply must match (Claude structured outputs, output_config.format).
Generated from the catalog so it cannot drift from the menu. Ranges go in descriptions, because
structured outputs do not support minimum/maximum; the checker enforces them.
compact=True is the default (default_compact(); VALORA_DIRECTOR_SCHEMA=full opts into the full shape).

Extension point for future kinds (research/physics/BLOCKS.md: field, sim): `wind` is the one optional
field ref (SINGLE_FIELDS, phase 5 Task 58 / hand-off H3); resolve_wind pins what the model sets. `sims`
joins LIST_FIELDS once engine/script.py accepts it.
A kind with no selectable block is simply left out, so an empty kind never breaks the schema."""
import os

from engine.catalog import KINDS
from engine.director.capabilities import BLOCK_ONLY_TAGS, KNOWN_TAGS
from engine.script import PURPOSES, TRANSITIONS

FORBIDDEN = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf", "minLength",
             "maxLength", "pattern", "$ref", "$defs", "definitions"}
# script field -> block kind. Required ones must have at least one selectable block in any catalog.
REF_KINDS = ("world", "lighting", "grade", "edit")
REQUIRED_REFS = ("world", "lighting", "grade")
LIST_FIELDS = {"effects": "effect"}  # future: "sims": "sim" once engine/script.py accepts it
SINGLE_FIELDS = {"wind": "field"}    # optional; the one shared wind (engine/physics/applies.resolve_wind)


def _obj(props, required):
    return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}


def _param(spec):
    if spec["type"] == "number":
        return {"type": "number", "description": f"{spec['min']:g}..{spec['max']:g}, default {spec['default']:g}"}
    if spec["type"] == "enum":
        return {"enum": list(spec["values"])}
    return {"type": "boolean"}


def _variant(m):
    params = _obj({k: _param(s) for k, s in m["params"].items()}, [])
    return _obj({"id": {"const": m["id"]}, "params": params}, ["id", "params"])


def _compact_ref(catalog, kind, ids):
    names = sorted({p for b in ids for p in catalog.get(kind, b)["params"]}) or ["none"]
    item = _obj({"name": {"enum": names}, "value": {"anyOf": [{"type": "number"}, {"type": "string"},
                                                               {"type": "boolean"}]}}, ["name", "value"])
    return _obj({"id": {"enum": ids}, "params": {"type": "array", "items": item}}, ["id", "params"])


def _ref(catalog, kind, compact):
    """Schema for one block reference, or None when the kind has no selectable block."""
    ids = catalog.selectable_ids(kind)
    if not ids:
        return None
    if compact:
        return _compact_ref(catalog, kind, ids)
    variants = [_variant(catalog.get(kind, b)) for b in ids]
    return variants[0] if len(variants) == 1 else {"anyOf": variants}


def harness_only_tags(catalog):
    """Tags only a harness-only control provides (camera.turntable): never offered to the model."""
    hidden, shown = set(), set()
    on = set(catalog.always_on())
    for kind in KINDS:
        sel = set(catalog.selectable_ids(kind))
        for b in catalog.ids(kind):
            m = catalog.get(kind, b)
            if m.get("landsIn"):   # a phase-5 block waiting to be switched on (Task 88): its asks stay askable
                continue
            tags = set(m.get("capabilities", []))
            (shown if b in sel or (kind, b) in on else hidden).update(tags)
    return hidden - shown


def capability_enum(catalog):
    """Every tag a user can ask for (vocabulary tags with phrases, including ones nothing delivers yet)
    plus 'other'. Block-only tags describe what blocks do and are never asks; harness-only controls
    are never offered. The pipeline (capabilities.merge_llm) drops any tag the catalog can deliver."""
    return sorted(KNOWN_TAGS - BLOCK_ONLY_TAGS - harness_only_tags(catalog)) + ["other"]


def scene_output_schema(catalog, compact=False):
    target = {"anyOf": [_obj({"marker": {"type": "string"}}, ["marker"]),
                        _obj({"detail": {"type": "integer"}}, ["detail"])]}
    shot = _obj({"startS": {"type": "number"}, "endS": {"type": "number"},
                 "purpose": {"enum": list(PURPOSES)}, "transitionIn": {"enum": list(TRANSITIONS)},
                 "focus": {"enum": ["subject"]}, "target": target,
                 "camera": _ref(catalog, "camera", compact)},
                ["startS", "endS", "purpose", "camera"])
    unsupported = _obj({"ask": {"type": "string"}, "capability": {"enum": capability_enum(catalog)}},
                       ["ask", "capability"])
    subject = _obj({"placement": {"enum": ["ground", "float"]}, "motion": _ref(catalog, "motion", compact)},
                   ["placement", "motion"])
    props = {"assumptions": {"type": "array", "items": {"type": "string"}},
             "unsupported": {"type": "array", "items": unsupported},
             "subject": subject}
    required = ["assumptions", "unsupported", "subject", *REQUIRED_REFS]
    for k in REF_KINDS:
        ref = _ref(catalog, k, compact)
        if ref is not None:
            props[k] = ref
    for field, kind in SINGLE_FIELDS.items():
        ref = _ref(catalog, kind, compact)
        if ref is not None:
            props[field] = ref
    for field, kind in LIST_FIELDS.items():
        ref = _ref(catalog, kind, compact)
        if ref is not None:
            props[field] = {"type": "array", "items": ref}
            required.append(field)
    props["shots"] = {"type": "array", "items": shot}
    required.append("shots")
    return _obj(props, required)


# Structured-output compile limits (eng): recalled from the structured-outputs docs (24 optional
# properties, 16 union-typed properties across the request); the public page did not state them on
# 2026-09-25. The pipeline switches to the compact schema when the API rejects the full one as too
# complex (LLMError.kind == "schema_too_complex"); Task 32's live smoke settles the real numbers.
COMPLEXITY_LIMITS = {"optional": 24, "unions": 16}
# The full schema exceeds those believed limits (69 optional on the 2026-09-25 catalog), so the
# director sends the COMPACT schema by default. VALORA_DIRECTOR_SCHEMA=full opts into the full one
# (then a "too complex" rejection still falls back to compact once). Task 32's first live step probes
# full vs compact and flips this default if the API accepts the full schema.
SCHEMA_ENV = "VALORA_DIRECTOR_SCHEMA"


def default_compact(env=None):
    """True unless the environment asks for the full schema (VALORA_DIRECTOR_SCHEMA=full)."""
    env = os.environ if env is None else env
    return env.get(SCHEMA_ENV, "").strip().lower() != "full"


def schema_complexity(schema):
    """{optional: properties not in their object's `required`, unions: anyOf nodes and type lists},
    counted over the whole tree (each anyOf variant counts on its own)."""
    out = {"optional": 0, "unions": 0}

    def walk(s):
        if isinstance(s, list):
            for x in s:
                walk(x)
            return
        if not isinstance(s, dict):
            return
        if "anyOf" in s or isinstance(s.get("type"), list):
            out["unions"] += 1
        if isinstance(s.get("properties"), dict):
            out["optional"] += len(set(s["properties"]) - set(s.get("required", [])))
            walk(list(s["properties"].values()))
        for k in ("items", "anyOf"):
            if k in s:
                walk(s[k])

    walk(schema)
    return out


def schema_problems(schema, path="$"):
    probs = []
    if isinstance(schema, dict):
        bad = FORBIDDEN & set(schema)
        if bad:
            probs.append(f"{path}: unsupported keywords {sorted(bad)}")
        if schema.get("type") == "object":
            if schema.get("additionalProperties") is not False:
                probs.append(f"{path}: objects need additionalProperties false")
            missing = set(schema.get("required", [])) - set(schema.get("properties", {}))
            if missing:
                probs.append(f"{path}: required names no property {sorted(missing)}")
        for k, v in schema.items():
            if k == "properties":
                for name, sub in v.items():
                    if sub is None:
                        probs.append(f"{path}.{name}: empty schema")
                    probs += schema_problems(sub, f"{path}.{name}")
            elif isinstance(v, (dict, list)):
                probs += schema_problems(v, f"{path}/{k}")
    elif isinstance(schema, list):
        for i, v in enumerate(schema):
            probs += schema_problems(v, f"{path}[{i}]")
    return probs


def conforms(x, s):
    """Minimal validator for the subset of JSON Schema this module emits (tests and fixtures)."""
    if "anyOf" in s:
        return any(conforms(x, v) for v in s["anyOf"])
    if "const" in s:
        return x == s["const"]
    if "enum" in s:
        return x in s["enum"]
    t = s.get("type")
    if t == "object":
        return (isinstance(x, dict) and set(s["required"]) <= set(x) and set(x) <= set(s["properties"])
                and all(conforms(v, s["properties"][k]) for k, v in x.items()))
    if t == "array":
        return isinstance(x, list) and all(conforms(v, s["items"]) for v in x)
    if t == "number":
        return isinstance(x, (int, float)) and not isinstance(x, bool)
    if t == "integer":
        return isinstance(x, int) and not isinstance(x, bool)
    if t == "string":
        return isinstance(x, str)
    if t == "boolean":
        return isinstance(x, bool)
    return False


def _undo(ref):
    if isinstance(ref, dict) and isinstance(ref.get("params"), list):
        ref["params"] = {p["name"]: p["value"] for p in ref["params"]
                         if isinstance(p, dict) and isinstance(p.get("name"), str) and "value" in p}
    return ref


def _list(v):
    return v if isinstance(v, list) else []


def decompact(raw):
    """Compact replies carry params as [{name, value}]; turn them back into objects. Tolerates junk."""
    if not isinstance(raw, dict):
        return raw
    for k in (*REF_KINDS, *SINGLE_FIELDS):
        _undo(raw.get(k))
    subj = raw.get("subject")
    _undo(subj.get("motion") if isinstance(subj, dict) else None)
    for field in LIST_FIELDS:
        for ref in _list(raw.get(field)):
            _undo(ref)
    for sh in _list(raw.get("shots")):
        if isinstance(sh, dict):
            _undo(sh.get("camera"))
    return raw
