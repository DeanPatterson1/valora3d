"""Rulebook part 2: taste guide v1. Rules are data (taste/rules.json); corpus numbers are filled
from research/corpus/stats.json only when trusted with n >= MIN_STAT_N, else fallbackText is used."""
import json
import re
from pathlib import Path

from engine.director.family import FAMILIES

ROOT = Path(__file__).resolve().parents[2]
TASTE_FILE = Path(__file__).with_name("taste") / "rules.json"
CRAFT_DIR = ROOT / "research" / "craft"
REFS_DIR = ROOT / "research" / "corpus" / "refs"
STATS = ROOT / "research" / "corpus" / "stats.json"
MIN_STAT_N = 5
FAMILY_ORDER = ("any",) + FAMILIES
_CRAFT = re.compile(r"\*\*([VPFC]-[A-Z]{1,2}\d{2}) \[T\d\]")
_TIERS = re.compile(r"\*\*((?:B-\d{2})|(?:T\d-X?\d{1,2})) \[")
_SECTION = re.compile(r"^(?:spec|PILOT-NOTES)§[0-9a-z.]+$")
_STAT = re.compile(r"\{stat:([a-z]+)\.([A-Za-z0-9]+)(?:\.(median|p25|p75))?\}")


def load_rules(path=TASTE_FILE):
    return json.loads(path.read_text(encoding="utf-8"))


def known_cites():
    ids = set()
    for f in CRAFT_DIR.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        ids |= set(_CRAFT.findall(text)) | set(_TIERS.findall(text))
    return ids | {p.stem for p in REFS_DIR.glob("*.json")}


def _block_ok(ref, catalog):
    path, _, param = ref.partition(".")
    kind, _, bid = path.partition("/")
    m = catalog.get(kind, bid) if kind and bid else None
    return m is not None and (not param or param in m["params"])


def validate_rules(rules, catalog, cites=None):
    cites = known_cites() if cites is None else cites
    probs, seen = [], set()
    for r in rules:
        rid = r.get("id")
        if rid in seen:
            probs.append(f"{rid}: duplicate id")
        seen.add(rid)
        if r.get("family") not in FAMILY_ORDER:
            probs.append(f"{rid}: family must be one of {FAMILY_ORDER}")
        if not r.get("text") or len(r["text"]) > 400:
            probs.append(f"{rid}: text must be 1-400 characters")
        if not r.get("cites"):
            probs.append(f"{rid}: cites nothing (spec §9a: every rule cites its source)")
        for c in r.get("cites", []):
            if c not in cites and not _SECTION.match(c):
                probs.append(f"{rid}: unknown cite {c}")
        for b in r.get("blocks", []):
            if not _block_ok(b, catalog):
                probs.append(f"{rid}: {b} is not a block/param in the catalog")
        holders = _STAT.findall(r.get("text", ""))
        if "{stat:" in r.get("text", "") and (not holders or not r.get("fallbackText")):
            probs.append(f"{rid}: a {{stat:...}} placeholder needs a valid path and a fallbackText")
    return probs


def _stat(stats, fam, name, field):
    s = (stats.get("families", {}).get(fam) or {}).get(name)
    if not s or s.get("trusted") is not True or s.get("n", 0) < MIN_STAT_N:
        return None
    if field:
        return f"{s[field]:g}" if field in s else None
    top = sorted(s.get("shares", {}).items(), key=lambda kv: -kv[1])[:4]
    return ", ".join(f"{k} {round(v * 100)}%" for k, v in top) or None


def _render_rule(r, stats):
    text, ns = r["text"], []
    for m in _STAT.finditer(r["text"]):
        v = _stat(stats, *m.groups())
        if v is None:
            return r["fallbackText"]
        fam, name, _ = m.groups()
        ns.append(stats["families"][fam][name]["n"])
        text = text.replace(m.group(0), v)
    if ns:
        text += f" (n={min(ns)}, corpus {stats.get('recordSetHash', '?')})"
    return text


def render_taste(rules, stats):
    lines = ["# 2. Taste guide v1",
             "Craft rules. Each cites where it came from: craft rule ids (research/craft), TIERS items, "
             "reference clips (refNN and corpus ids). Numbers from the corpus show their sample size."]
    for fam in FAMILY_ORDER:
        rows = [r for r in rules if r["family"] == fam]
        if rows:
            lines.append(f"\n## {'All subjects' if fam == 'any' else fam.capitalize() + 's'}")
            lines += [f"- {r['id']} {_render_rule(r, stats)} [{', '.join(r['cites'])}]" for r in rows]
    return "\n".join(lines) + "\n"
