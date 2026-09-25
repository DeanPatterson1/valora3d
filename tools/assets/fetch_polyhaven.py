"""Download CC0 Poly Haven assets into assets-in/library/polyhaven/ and pin them in engine/assets/manifest.json
(owner-approved 2026-09-25 art pass: free Poly Haven CC0 only, nothing from any other site).

Every file comes from the official API's file list (api.polyhaven.com/files/<slug>), is checked against the
md5 the API publishes for it, then pinned by sha256 like every other manifest entry (engine.assets.resolve()
re-hashes on load). Poly Haven publishes every asset under CC0 (https://polyhaven.com/license); the entry
records that proof URL, the asset page and the retrieval date.

  py tools/assets/fetch_polyhaven.py hdri <slug> [--res 4k]
  py tools/assets/fetch_polyhaven.py model <slug> [--res 1k] [--extra dry_diff]
  py tools/assets/fetch_polyhaven.py texture <slug> [--res 2k] [--maps diff,rough,nor_gl]

Ids: an HDRI is <slug>_<res>; a glTF is <slug>_<res> and its buffer <slug>_bin; every other file is its stem
(e.g. grass_medium_02_diff_1k, concrete_pavement_nor_gl_2k)."""
import argparse
import datetime
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engine.assets import contained, validate_manifest  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "assets-in" / "library"
MANIFEST = REPO / "engine" / "assets" / "manifest.json"
API = "https://api.polyhaven.com"
HOSTS = ("https://dl.polyhaven.org/", "https://api.polyhaven.com/")
LICENCE_PROOF = "https://polyhaven.com/license"
UA = {"User-Agent": "valora-assets/1 (CC0 pinning)"}


def _get(url, binary=False):
    if not url.startswith(HOSTS):
        raise SystemExit(f"refusing non-Poly-Haven URL {url}")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        data = r.read()
    return data if binary else json.loads(data)


def _hash(b, algo):
    return hashlib.new(algo, b).hexdigest()


def _fetch(url, md5, rel, aid, slug, doc):
    dst = contained(LIB, rel, aid)
    if dst.exists() and _hash(dst.read_bytes(), "md5") == md5:
        data = dst.read_bytes()
    else:
        data = _get(url, binary=True)
        if _hash(data, "md5") != md5:
            raise SystemExit(f"{aid}: md5 mismatch against the Poly Haven API record")
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
    doc["assets"][aid] = {"path": rel, "sha256": _hash(data, "sha256"), "licence": "CC0-1.0",
                          "source": f"https://polyhaven.com/a/{slug}", "credit": None, "md5": md5,
                          "licenceProof": LICENCE_PROOF, "retrieved": datetime.date.today().isoformat()}
    print(f"  {aid}: {rel} ({len(data) // 1024} KB)")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tools/assets/fetch_polyhaven.py")
    ap.add_argument("kind", choices=("hdri", "model", "texture"))
    ap.add_argument("slug")
    ap.add_argument("--res")
    ap.add_argument("--maps", default="diff,rough,nor_gl")
    ap.add_argument("--extra", default="", help="model: extra texture maps (comma list), e.g. dry_diff")
    a = ap.parse_args(argv)
    info = _get(f"{API}/info/{a.slug}")
    want_type = {"hdri": 0, "texture": 1, "model": 2}[a.kind]
    if info.get("type") != want_type:
        raise SystemExit(f"{a.slug} is Poly Haven type {info.get('type')}, not a {a.kind}")
    files = _get(f"{API}/files/{a.slug}")
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    base = f"polyhaven/{a.slug}"
    print(f"{a.kind} {a.slug} (CC0, {', '.join(info.get('authors', {}))})")
    if a.kind == "hdri":
        res = a.res or "4k"
        h = files["hdri"][res]["hdr"]
        _fetch(h["url"], h["md5"], f"polyhaven/{a.slug}_{res}.hdr", f"{a.slug}_{res}", a.slug, doc)
    elif a.kind == "model":
        res = a.res or "1k"
        g = files["gltf"][res]["gltf"]
        _fetch(g["url"], g["md5"], f"{base}/{a.slug}_{res}.gltf", f"{a.slug}_{res}", a.slug, doc)
        for rel, inc in g.get("include", {}).items():
            stem = Path(rel).stem
            aid = f"{a.slug}_bin" if rel.endswith(".bin") and stem == a.slug else stem
            _fetch(inc["url"], inc["md5"], f"{base}/{rel}", aid, a.slug, doc)
        for m in filter(None, a.extra.split(",")):
            j = files[m][res]["jpg"]
            _fetch(j["url"], j["md5"], f"{base}/textures/{a.slug}_{m}_{res}.jpg", f"{a.slug}_{m}_{res}", a.slug, doc)
    else:
        res = a.res or "2k"
        key = {"diff": "Diffuse", "rough": "Rough", "nor_gl": "nor_gl", "arm": "arm", "disp": "Displacement",
               "ao": "AO"}
        for m in a.maps.split(","):
            j = files[key.get(m, m)][res]["jpg"]
            _fetch(j["url"], j["md5"], f"{base}/{a.slug}_{m}_{res}.jpg", f"{a.slug}_{m}_{res}", a.slug, doc)
    doc["assets"] = dict(sorted(doc["assets"].items()))
    validate_manifest(doc)
    MANIFEST.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
