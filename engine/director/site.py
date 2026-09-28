"""The site delivery gate for ungraded blocks (phase 5, Task 88; owner decision pending, coordinator-recorded
recommendation: the harness and the dice may roll growth blocks whose `golden` is still null, the SITE may not
deliver them until the owner grades a render).

engine/catalog_growth.json holds each growth block's `golden` status. site_catalog() is the catalog the site
must call direct() with: every growth block that is not graded is taken off the menu, so the menu, the output
schema, the dice, the fallback and the capability notes all behave as if it did not exist (asks for it are
reported as unsupported, never delivered). site_deliverable() is the last check on a delivered script: it
names any ungraded block the script still uses, so a caller that forgot site_catalog() still cannot ship one.
apps/web is not connected to the director yet (`not_connected`); when it is wired it must use both."""
import copy
import json
from pathlib import Path

from engine.catalog import Catalog

GROWTH_FILE = Path(__file__).resolve().parents[1] / "catalog_growth.json"


def load_growth(path=GROWTH_FILE):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def ungraded(growth=None):
    """Growth block refs ('kind/id') whose golden status is still null."""
    growth = growth or load_growth()
    return sorted(ref for ref, e in growth["blocks"].items() if not e.get("golden"))


def site_catalog(catalog=None, growth=None):
    """A catalog with every ungraded growth block off the menu (directorSelectable false). A given catalog is
    copied, never patched: a shared harness/server catalog keeps its growth blocks (review chunk7 #5)."""
    growth = growth or load_growth()
    cat = Catalog(copy.deepcopy(catalog._blocks), catalog._root) if catalog is not None else Catalog.load()
    for ref in ungraded(growth):
        key = tuple(ref.split("/"))
        m = cat._blocks.get(key)
        if m is not None:
            m["directorSelectable"] = False
    for wid, light in site_lighting(growth).items():
        w, m = cat._blocks.get(("world", wid)), cat._blocks.get(("lighting", light["id"]))
        if w is None or m is None or light["id"] not in (w.get("lightingPairs") or [light["id"]]):
            continue
        w["siteLighting"] = copy.deepcopy(light)     # the fallback lights this world as the owner graded it
        m["directorSelectable"] = True               # graded, so on the site menu (practicals_only is harness-off)
    return cat


def site_lighting(growth=None):
    """{world id: {"id", "params"}}: each graded world's owner-graded lighting (catalog_growth.json siteLighting)."""
    growth = growth or load_growth()
    return {k: v for k, v in (growth.get("siteLighting") or {}).items() if isinstance(v, dict) and "id" in v}


def _refs(script):
    out = [(k, script.get(k)) for k in ("world", "lighting", "grade", "edit")]
    w = script.get("wind")
    if isinstance(w, dict) and (w.get("pinned") or "pinned" not in w):   # the checker's still-air default is not a
        out.append(("field", w))                                         # choice; a wind the script set is
    out.append(("motion", (script.get("subject") or {}).get("motion")))
    out += [("effect", e) for e in script.get("effects") or []]
    out += [("camera", sh.get("camera")) for sh in script.get("shots") or [] if isinstance(sh, dict)]
    return {f"{k}/{r['id']}" for k, r in out if isinstance(r, dict) and isinstance(r.get("id"), str)}


def site_deliverable(script, growth=None):
    """[] when the site may deliver this script, else the ungraded growth blocks it uses. The checker's own
    couplings (rain adds wet_surface) count too: a coupled ungraded block is still ungraded."""
    return sorted(_refs(script) & set(ungraded(growth)))


def site_rulebook(catalog=None, growth=None):
    """(text, version) of the rulebook built from site_catalog(): its menu never lists an ungraded block, so the
    system prompt and the output schema agree on the site (pass it to direct(rulebook=...))."""
    from engine.director.rulebook import build_rulebook, version
    text = build_rulebook(site_catalog(catalog, growth))
    return text, version(text)
