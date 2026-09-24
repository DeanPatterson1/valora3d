"""Block catalog: every world/lighting/camera/motion/effect/grade the director may use.

The rulebook's menu is generated from these manifests (phase 3), so what the AI reads and
what the code builds cannot drift apart.
"""
import importlib.util
import json
from pathlib import Path

KINDS = ("world", "lighting", "camera", "motion", "effect", "grade")
ASPECTS = ("9:16", "16:9", "1:1", "4:5")
BLOCKS_DIR = Path(__file__).parent / "blocks"
_REQUIRED = ("id", "kind", "description", "params", "subjectSizeM", "aspects", "costWeight", "tags")
_CAMERA_PARAMS = ("distance", "lensMm", "fstop")


class CatalogError(ValueError):
    pass


def _check_param(where, name, spec):
    t = spec.get("type")
    if t == "number":
        lo, hi, d = spec.get("min"), spec.get("max"), spec.get("default")
        if not all(isinstance(v, (int, float)) for v in (lo, hi, d)):
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
    missing = [k for k in _REQUIRED if k not in m]
    if missing:
        raise CatalogError(f"{where}: missing keys {missing}")
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


class Catalog:
    def __init__(self, blocks, root):
        self._blocks = blocks  # {(kind, id): manifest}
        self._root = root

    @classmethod
    def load(cls, root=None):
        root = Path(root) if root else BLOCKS_DIR
        blocks = {}
        for kind in KINDS:
            kdir = root / kind
            if not kdir.is_dir():
                continue
            for bdir in sorted(p for p in kdir.iterdir() if p.is_dir()):
                mf = bdir / "block.json"
                if not mf.exists():
                    continue
                m = json.loads(mf.read_text(encoding="utf-8"))
                _check_manifest(kind, bdir.name, m)
                blocks[(kind, bdir.name)] = m
        return cls(blocks, root)

    def get(self, kind, bid):
        return self._blocks.get((kind, bid))

    def ids(self, kind):
        return [b for (k, b) in self._blocks if k == kind]

    def load_camera_path(self, bid):
        """Import engine/blocks/camera/<id>/path.py and return its sample() function."""
        f = self._root / "camera" / bid / "path.py"
        spec = importlib.util.spec_from_file_location(f"valora_camera_{bid}", f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.sample
