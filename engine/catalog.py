"""Block catalog: every world/lighting/camera/motion/effect/grade the director may use.

The rulebook's menu is generated from these manifests (phase 3), so what the AI reads and
what the code builds cannot drift apart.
"""
import copy
import importlib.util
import json
from pathlib import Path

KINDS = ("world", "lighting", "camera", "motion", "effect", "grade", "edit")
TIERS = ("T1", "T2", "T3", "T4")
ASPECTS = ("9:16", "16:9", "1:1", "4:5")
BLOCKS_DIR = Path(__file__).parent / "blocks"
_REQUIRED = ("id", "kind", "description", "params", "subjectSizeM", "aspects", "costWeight", "tags",
             "tierMax")
_CAMERA_PARAMS = ("distance", "lensMm", "fstop")
# CameraBench move names: the starter blocks' own values (arc, dolly) plus the standard set.
CAMERA_MOVES = ("static", "pan", "tilt", "dolly_in", "dolly_out", "truck", "pedestal", "arc",
                "orbit", "crane", "zoom_in", "zoom_out", "roll", "track", "push_in", "pull_out",
                "dolly")


class CatalogError(ValueError):
    pass


_TAG_KEYS = ("mood", "energy", "palette")


def _is_num(v):
    """True for int/float but not bool (bool is an int subclass)."""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check_types(where, m):
    if not isinstance(m["params"], dict):
        raise CatalogError(f"{where}: params must be an object")
    for name, spec in m["params"].items():
        if not isinstance(spec, dict):
            raise CatalogError(f"{where}: param '{name}' spec must be an object")
    size = m["subjectSizeM"]
    if not (isinstance(size, list) and len(size) == 2 and all(_is_num(v) for v in size)):
        raise CatalogError(f"{where}: subjectSizeM must be a list of 2 numbers")
    if not isinstance(m["aspects"], list):
        raise CatalogError(f"{where}: aspects must be a list")
    cw = m["costWeight"]
    if not _is_num(cw) or cw <= 0:
        raise CatalogError(f"{where}: costWeight must be a number > 0")
    tags = m["tags"]
    if not isinstance(tags, dict) or set(tags) != set(_TAG_KEYS):
        raise CatalogError(f"{where}: tags must have exactly the keys {list(_TAG_KEYS)}")
    for k in _TAG_KEYS:
        v = tags[k]
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            raise CatalogError(f"{where}: tags.{k} must be a list of strings")
    if m["tierMax"] not in TIERS:
        raise CatalogError(f"{where}: tierMax must be one of {list(TIERS)}")


def _check_param(where, name, spec):
    t = spec.get("type")
    if t == "number":
        lo, hi, d = spec.get("min"), spec.get("max"), spec.get("default")
        if not all(_is_num(v) for v in (lo, hi, d)):
            raise CatalogError(f"{where}: param '{name}' needs numeric min/max/default")
        if lo > hi:
            raise CatalogError(f"{where}: param '{name}' min > max")
        if not lo <= d <= hi:
            raise CatalogError(f"{where}: param '{name}' default outside [{lo}, {hi}]")
    elif t == "enum":
        vals = spec.get("values")
        if not vals or spec.get("default") not in vals:
            raise CatalogError(f"{where}: param '{name}' enum needs values containing default")
    elif t == "bool":
        if not isinstance(spec.get("default"), bool):
            raise CatalogError(f"{where}: param '{name}' bool needs a bool default")
    else:
        raise CatalogError(f"{where}: param '{name}' has unknown type {t!r}")


def _check_manifest(folder_kind, folder_id, m):
    where = f"{folder_kind}/{folder_id}"
    if not isinstance(m, dict):
        raise CatalogError(f"{where}: block.json must be an object")
    missing = [k for k in _REQUIRED if k not in m]
    if missing:
        raise CatalogError(f"{where}: missing keys {missing}")
    _check_types(where, m)
    if m["id"] != folder_id:
        raise CatalogError(f"{where}: id '{m['id']}' does not match folder '{folder_id}'")
    if m["kind"] != folder_kind:
        raise CatalogError(f"{where}: kind '{m['kind']}' does not match folder '{folder_kind}'")
    lo, hi = m["subjectSizeM"]
    if not 0 < lo <= hi:
        raise CatalogError(f"{where}: bad subjectSizeM")
    bad = [a for a in m["aspects"] if a not in ASPECTS]
    if bad:
        raise CatalogError(f"{where}: unknown aspects {bad}")
    for name, spec in m["params"].items():
        _check_param(where, name, spec)
    if folder_kind == "camera":
        lacking = [p for p in _CAMERA_PARAMS if p not in m["params"]]
        if m.get("framing") not in ("full", "detail") or lacking:
            raise CatalogError(f"camera '{folder_id}' missing framing or params {lacking}")
        if not m["params"]["distance"].get("min", 0) > 0:
            raise CatalogError(f"camera '{folder_id}': distance min must be > 0")
        if "move" in m:
            _check_move(folder_id, m)


def _check_move(folder_id, m):
    """`move` is a CameraBench name, or {param, map} naming the move per value of an enum param
    (e.g. macro_detail: slide -> truck, push -> dolly)."""
    mv = m["move"]
    if isinstance(mv, dict):
        spec = m["params"].get(mv.get("param"))
        mp = mv.get("map")
        if (set(mv) != {"param", "map"} or not spec or spec.get("type") != "enum"
                or not isinstance(mp, dict) or set(mp) != set(spec["values"])):
            raise CatalogError(f"camera '{folder_id}': move map must name an enum param and map every value")
        names = list(mp.values())
    else:
        names = [mv]
    for name in names:
        if not isinstance(name, str) or name not in CAMERA_MOVES:
            raise CatalogError(f"camera '{folder_id}': move {name!r} not in {list(CAMERA_MOVES)}")


class Catalog:
    def __init__(self, blocks, root):
        self._blocks = blocks  # {(kind, id): manifest}
        self._root = root
        self._camera_paths = {}  # {id: sample}

    @classmethod
    def load(cls, root=None):
        root = Path(root) if root else BLOCKS_DIR
        blocks = {}
        if root.is_dir():
            unknown = sorted(p.name for p in root.iterdir() if p.is_dir() and p.name not in KINDS)
            if unknown:
                raise CatalogError(f"{root}: unknown kind folder(s) {unknown}; expected {list(KINDS)}")
        for kind in KINDS:
            kdir = root / kind
            if not kdir.is_dir():
                continue
            for bdir in sorted(p for p in kdir.iterdir() if p.is_dir()):
                mf = bdir / "block.json"
                if not mf.is_file():
                    raise CatalogError(f"{kind}/{bdir.name}: missing block.json")
                try:
                    m = json.loads(mf.read_text(encoding="utf-8-sig"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
                    raise CatalogError(f"{kind}/{bdir.name}: bad block.json: {e}") from e
                _check_manifest(kind, bdir.name, m)
                blocks[(kind, bdir.name)] = m
        return cls(blocks, root)

    def get(self, kind, bid):
        return copy.deepcopy(self._blocks.get((kind, bid)))

    def ids(self, kind):
        return [b for (k, b) in self._blocks if k == kind]

    def load_camera_path(self, bid):
        """Import engine/blocks/camera/<id>/path.py and return its sample() function."""
        if not isinstance(bid, str) or not bid or "/" in bid or "\\" in bid or ".." in bid:
            raise CatalogError(f"camera id {bid!r} is not a valid block id")
        if bid in self._camera_paths:
            return self._camera_paths[bid]
        if ("camera", bid) not in self._blocks:
            raise CatalogError(f"unknown camera '{bid}'")
        f = self._root / "camera" / bid / "path.py"
        if not f.is_file():
            raise CatalogError(f"camera/{bid}: missing path.py")
        spec = importlib.util.spec_from_file_location(f"valora_camera_{bid}", f)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            raise CatalogError(f"camera/{bid}: path.py failed to import: {e}") from e
        sample = getattr(mod, "sample", None)
        if not callable(sample):
            raise CatalogError(f"camera/{bid}: path.py has no callable sample()")
        self._camera_paths[bid] = sample
        return sample
