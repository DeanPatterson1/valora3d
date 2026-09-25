"""Seeds whose dice roll agrees with a canned reply. Tests that feed a fixed example reply (first pass,
craft fixes, hostile echo) are about the reply, not the dice; they pick a seed whose rolled direction
the reply already follows, so a change in the seeded roll never turns them into repair/fallback tests."""
import copy

from engine.catalog import Catalog
from engine.director.adherence import drift
from engine.director.job import make_job
from engine.tests.test_director_package import _p


def phase4_catalog():
    """The catalog with the phase-5 growth blocks off the menu except field/wind (selectable since Task 58): the
    studio-only, dry, still-air dice of phase 4. Tests about a canned REPLY (not about the dice) run on it, since
    the grown dice rarely roll the one direction a fixed studio reply follows (Task 87/88)."""
    import json
    from pathlib import Path
    cat = Catalog.load()
    growth = json.loads((Path(__file__).resolve().parents[1] / "catalog_growth.json").read_text(encoding="utf-8"))
    for ref in growth["blocks"]:
        if ref != "field/wind":
            cat._blocks[tuple(ref.split("/"))]["directorSelectable"] = False
    return cat


def seed_matching(reply, prompts, model="pocket_watch", *, markers=None, duration=None, start=0, limit=500,
                  runs=1, catalog=None):
    """First s >= start such that seeds s..s+runs-1 roll, for every prompt, a direction `reply` shows no
    drift from (world, opener, measured cadence, the direction paths). A prompt may be (text, markers)."""
    cat, p = catalog or Catalog.load(), _p(model)
    prompts = [prompts] if isinstance(prompts, str) else list(prompts)
    prompts = [pr if isinstance(pr, tuple) else (pr, markers) for pr in prompts]
    for s in range(start, start + limit):
        if all(_agrees(reply, make_job(pr, p, cat, seed=s + k, markers=mk, duration=duration), cat)
               for pr, mk in prompts for k in range(runs)):
            return s
    raise AssertionError(f"no seed in {start}..{start + limit} rolls a direction this reply follows")


def _agrees(reply, job, cat):
    s = copy.deepcopy(reply)
    s["format"] = job.fmt
    return not drift(s, job.direction, cat)
