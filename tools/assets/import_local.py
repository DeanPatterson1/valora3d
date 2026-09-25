"""Copy the CC0 Poly Haven files render-studio already pinned into assets-in/library/polyhaven/ and write
their entries into engine/assets/manifest.json (phase 5 Task 62).

A LOCAL COPY of files already on disk: it downloads nothing. Only the 4k HDRI is imported (not the 8k).
A file whose render-studio record is not CC0, or whose md5 no longer matches that record, is skipped and
listed (owner-only). ModVision's render-studio is read, never written (spec §2).
Run: py tools/assets/import_local.py [--source <render-studio assets dir>]"""
import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCE = Path(r"C:\Users\deand\Projects\ModVision\tools\render-studio\assets")
DEST = REPO / "assets-in" / "library" / "polyhaven"
MANIFEST = REPO / "engine" / "assets" / "manifest.json"
WANTED = ("cloudy_vondelpark_hdri_4k.hdr", "asphalt_02_", "tree_small_02/", "grass_medium_01/")
RENAME = {"cloudy_vondelpark_hdri_4k": "cloudy_vondelpark_4k", "asphalt_02_Diffuse_2k": "asphalt_02_diff",
          "asphalt_02_Rough_2k": "asphalt_02_rough", "asphalt_02_nor_gl_2k": "asphalt_02_nor_gl",
          "asphalt_02_Displacement_2k": "asphalt_02_disp"}


def _hash(p, algo):
    h = hashlib.new(algo)
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def asset_id(rel):
    p = Path(rel)
    stem = RENAME.get(p.stem, p.stem)
    return f"{stem}_bin" if p.suffix == ".bin" else stem


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tools/assets/import_local.py")
    ap.add_argument("--source", type=Path, default=SOURCE)
    a = ap.parse_args(argv)
    records = json.loads((a.source / "manifest.json").read_text(encoding="utf-8"))
    doc = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {"schema": "valora.assets/1", "assets": {}}
    skipped = []
    for r in records:
        rel = r["file"]
        if not rel.startswith(WANTED):
            continue
        src = a.source / rel
        if r.get("license") != "CC0":
            skipped.append(f"{rel}: licence {r.get('license')!r} is not CC0")
            continue
        if not src.exists() or _hash(src, "md5") != r.get("md5"):
            skipped.append(f"{rel}: missing or md5 differs from render-studio's record")
            continue
        dst = DEST / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)                              # copy, never move
        slug = re.sub(r"^https://polyhaven\.com/a/", "", r["source"])
        doc["assets"][asset_id(rel)] = {"path": f"polyhaven/{rel}", "sha256": _hash(dst, "sha256"),
                                        "licence": "CC0-1.0", "source": f"https://polyhaven.com/a/{slug}",
                                        "credit": None}
    doc["assets"] = dict(sorted(doc["assets"].items()))
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(doc['assets'])} assets pinned in {MANIFEST.relative_to(REPO)}")
    for s in skipped:
        print("SKIPPED (owner-only):", s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
