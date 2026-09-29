"""The site's local render job: one call from a web front end's render server to a finished frame sequence.

    py -m engine.site_job worlds
    py -m engine.site_job run --model SNAPSHOT.glb --out DIR [--prompt TEXT] [--world ID] [--aspect 9:16|16:9]
                              [--tier preview|final] [--seed N] [--duration S] [--frame-step K]
                              [--paint '#rrggbb'] [--finish gloss|metallic|satin|matte]
                              [--provider anthropic|fake:FIXTURE]

`worlds` prints the worlds the site may offer (site_catalog(): only owner-graded growth blocks are on the menu),
each with its description, aspects and golden still. `run` is ingest -> direct -> render, all on the site
catalog: the subject is the caller's true-scale GLB, the director works from site_catalog() + site_rulebook(),
a chosen world is pinned by avoiding every other world, and site_deliverable() is checked before Blender starts
(a script still naming an ungraded block is re-directed with the next seed, never rendered). The frames land in
DIR/frames/frame_000001.png... contiguously, so a caller encodes them at `fps` with one ffmpeg pattern.

Progress: one `SITEJOB {json}` line per stage on stdout ({"stage": "ingest" | "direct" | "render" | "done"}); the
render stage names the frame count and DIR/render/beauty, which the caller may watch for finished frames. The
last line is `SITEJOB {"stage": "done", ...}` or `SITEJOB {"stage": "error", "error": ...}` (exit 1). Exit codes
follow engine/__main__.py: 0 ok, 1 error, 2 usage, 5 input rejected.

The web app side (apps/web) is still `not_connected`; this module is the seam for a local render server."""
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

EXIT_OK, EXIT_ERROR, EXIT_BAD_INPUT = 0, 1, 5
TIERS = ("preview", "final")
ASPECTS = ("9:16", "16:9")
ASPECT_WORD = {"9:16": "vertical 9:16", "16:9": "landscape 16:9"}
MAX_REROLLS = 4
REPO = Path(__file__).resolve().parents[1]


def emit(stage, **fields):
    print("SITEJOB " + json.dumps({"stage": stage, **fields}), flush=True)


def worlds(catalog=None, growth=None):
    """The site's worlds in catalog order: id, description, aspects and the golden still (repo-relative, None
    for the always-on studio)."""
    from engine.director.site import load_growth, site_catalog
    growth = growth or load_growth()
    cat = site_catalog(catalog, growth)
    out = []
    for wid in cat.selectable_ids("world"):
        m = cat.get("world", wid)
        golden = (growth["blocks"].get(f"world/{wid}") or {}).get("golden")
        out.append({"id": wid, "description": m.get("description", ""), "aspects": list(m.get("aspects") or []),
                    "golden": golden})
    return out


def site_prompt(prompt, aspect):
    """The user's words, with the chosen aspect as a format pin when the words name none (engine.director.intent
    reads the aspect from the prompt; a prompt that names one keeps it)."""
    from engine.director.intent import read_pins
    prompt = " ".join((prompt or "").split())
    if aspect is None or "aspect" in read_pins(prompt):
        return prompt
    return f"{prompt} ({ASPECT_WORD[aspect]})" if prompt else ASPECT_WORD[aspect]


def direct_site(prompt, profile, *, world=None, aspect=None, seed=None, duration=None, provider, catalog=None):
    """A deliverable site script. Returns (DirectorResult, rerolls). Raises DirectorInputError for a world the
    site does not offer, and RuntimeError when MAX_REROLLS seeds all name an ungraded block."""
    import secrets

    from engine.director.job import SEED_LIMIT, DirectorInputError
    from engine.director.pipeline import direct
    from engine.director.site import site_catalog, site_deliverable, site_rulebook
    cat = catalog if catalog is not None else site_catalog()
    offered = cat.selectable_ids("world")
    if world is not None and world not in offered:
        raise DirectorInputError(f"world {world!r} is not offered on the site ({', '.join(offered)})")
    avoid = {"world": [w for w in offered if w != world]} if world and len(offered) > 1 else None
    rulebook = site_rulebook(cat)
    seed = secrets.randbelow(SEED_LIMIT) if seed is None else seed
    text = site_prompt(prompt, aspect)
    last = None
    for n in range(MAX_REROLLS):
        res = direct(text, profile, provider=provider, seed=(seed + n) % SEED_LIMIT, catalog=cat, rulebook=rulebook,
                     duration=duration, avoid=avoid)
        last = site_deliverable(res.script)
        if not last and (world is None or res.script["world"]["id"] == world):
            return res, n
    if last:
        raise RuntimeError(f"the director kept using blocks the site does not deliver ({', '.join(last)})")
    # the dice relax an avoid list that leaves nothing viable: this world cannot frame this subject in this format
    # (measured 2026-09-28: night_street never frames the sports car at 16:9, 0 of 10 seeds)
    raise DirectorInputError(f"the director could not make a {world} clip for this model"
                             f"{' at ' + aspect if aspect else ''}; try another format or scene")


def _paint(color, finish):
    if not color:
        return None
    from engine.paint import validate_paint
    return validate_paint({"color": color, "finish": finish or "gloss"})


def contiguous_frames(beauty_dir, frames, dest):
    """Copy the rendered NNNN.png stills, in frame order, to dest/frame_000001.png... ; returns the count."""
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for i, f in enumerate(frames, 1):
        src = Path(beauty_dir) / f"{f:04d}.png"
        if not src.is_file():
            raise RuntimeError(f"Blender did not write frame {f}")
        shutil.copyfile(src, dest / f"frame_{i:06d}.png")
    return len(frames)


def run(a, provider=None, compile_scene=None, ingest=None):
    from engine.compiler.timeline import frame_count
    from engine.director.site import site_catalog
    from engine.profile import SubjectProfile
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    paint = _paint(a.paint, a.finish)          # PaintError before any Blender work
    t0 = time.perf_counter()
    timing = {}

    emit("ingest")
    if ingest is None:
        from engine.ingest.run import ingest
    profile_path = out / "profile.json"
    if a.profile:                                                   # a caller's cached profile of the same GLB
        profile = SubjectProfile.from_dict(json.loads(Path(a.profile).read_text(encoding="utf-8")))
    else:
        profile = ingest(a.model, out / "ingest")
    profile_path.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")
    timing["ingestS"] = round(time.perf_counter() - t0, 1)

    emit("direct")
    t1 = time.perf_counter()
    if provider is None:
        from engine.__main__ import _provider
        provider = _provider(a.provider)
    cat = site_catalog()
    res, rerolls = direct_site(a.prompt, profile, world=a.world, aspect=a.aspect, seed=a.seed,
                               duration=a.duration, provider=provider, catalog=cat)
    script = res.script
    (out / "script.json").write_text(json.dumps(script, indent=2), encoding="utf-8")
    from engine.__main__ import _provider_error
    summary = {"source": res.source, "direction": script["direction"], "world": script["world"]["id"],
               "format": script["format"], "unsupported": script.get("unsupported", []), "rerolls": rerolls,
               "providerError": _provider_error(res)}
    (out / "direct.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    timing["directS"] = round(time.perf_counter() - t1, 1)

    fmt = script["format"]
    step = max(1, int(a.frame_step))
    frames = list(range(1, frame_count(fmt) + 1, step))
    fps = fmt["fps"] / step
    emit("render", frames=len(frames), fps=fps, beauty=str(out / "render" / "beauty"), tier=a.tier,
         direct=summary)
    t2 = time.perf_counter()
    if compile_scene is None:
        from engine.compiler.run import compile_scene
    compile_scene(script, profile, a.model, out / "render", tier=a.tier, frames=frames, catalog=cat,
                  timeout_s=a.timeout, paint=paint, passes=False)   # mask/gloss/mist are for the harness, not the site
    timing["renderS"] = round(time.perf_counter() - t2, 1)
    n = contiguous_frames(out / "render" / "beauty", frames, out / "frames")
    timing["totalS"] = round(time.perf_counter() - t0, 1)
    result = {"frames": n, "fps": fps, "framesDir": str(out / "frames"), "tier": a.tier, "timing": timing,
              "direct": summary}
    (out / "site_job.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    emit("done", **result)
    return EXIT_OK


def main(argv=None):
    ap = argparse.ArgumentParser(prog="engine.site_job")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("worlds")
    r = sub.add_parser("run")
    r.add_argument("--model", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--profile", help="a SubjectProfile JSON of the same model (skips ingest)")
    r.add_argument("--prompt", default="")
    r.add_argument("--world")
    r.add_argument("--aspect", choices=ASPECTS)
    r.add_argument("--tier", default="preview", choices=TIERS)
    r.add_argument("--seed", type=int)
    r.add_argument("--duration", type=float)
    r.add_argument("--frame-step", type=int, default=1, help="render every Kth frame (the clip plays at fps/K)")
    r.add_argument("--paint", help="#rrggbb body colour (omit to keep the model's own materials)")
    r.add_argument("--finish", default="gloss")
    r.add_argument("--provider", default="anthropic")
    r.add_argument("--timeout", type=float, default=4 * 3600, help="Blender render timeout, seconds")
    a = ap.parse_args(argv)
    if a.cmd == "worlds":
        print(json.dumps({"worlds": worlds()}, indent=2))
        return EXIT_OK
    from engine.director.job import DirectorInputError
    from engine.paint import PaintError
    try:
        return run(a)
    except (DirectorInputError, PaintError) as e:
        emit("error", error=f"input rejected: {e}")
        return EXIT_BAD_INPUT
    except Exception as e:  # noqa: BLE001 - one line for the caller, never a traceback
        msg = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
        emit("error", error=msg)
        return EXIT_ERROR


if __name__ == "__main__":
    os.chdir(REPO)                      # the engine resolves assets and the catalog relative to the repo
    sys.exit(main())
