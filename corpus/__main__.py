"""py -m corpus queue seed | queue progress | queue next --category C [--n N] | accept DRAFT... | accuracy | tags | stats [--write] | backlog | ab list|scripts|record|render"""
import argparse
import json
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog="corpus")
    sub = ap.add_subparsers(dest="cmd", required=True)
    qp = sub.add_parser("queue")
    qp.add_argument("action", choices=["seed", "progress", "next"])
    qp.add_argument("--category")
    qp.add_argument("--n", type=int, default=5)
    ac = sub.add_parser("accept")
    ac.add_argument("drafts", nargs="+")
    sub.add_parser("accuracy")
    sub.add_parser("tags")
    st = sub.add_parser("stats")
    st.add_argument("--write", action="store_true")
    sub.add_parser("backlog")
    abp = sub.add_parser("ab")
    abp.add_argument("action", choices=["list", "scripts", "record", "render"])
    abp.add_argument("--pair")
    abp.add_argument("--yes", action="store_true", help="the owner confirmed rendering")
    a = ap.parse_args(argv)
    if a.cmd == "ab":
        from corpus import ab
        if a.action == "list":
            for p in ab.PAIRS:
                print(p["name"], p["model"], p["path"])
            return 0
        pair = ab.by_name(a.pair)
        if a.action == "scripts":
            print(json.dumps(dict(zip("ab", ab.scripts_for(pair))), indent=1))
        elif a.action == "record":
            from engine.catalog import Catalog
            print(ab.write_draft(pair, Catalog.load()))
        else:
            if not a.yes:
                print("Owner-gated: confirm with the owner before rendering, then pass --yes")
                return 2
            for out in ab.render(pair):
                print(out)
        return 0
    if a.cmd == "backlog":
        from corpus.backlog import main as backlog_main
        return backlog_main()
    if a.cmd == "stats":
        from corpus import CORPUS_DIR, REFS_DIR
        from corpus.stats import compute, load_trust
        records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(REFS_DIR.glob("*.json"))]
        trusted = load_trust(CORPUS_DIR / "accuracy.json")
        s = compute(records, trusted=trusted)
        text = json.dumps(s, indent=1, sort_keys=True) + "\n"
        print(text, end="")
        if a.write:
            (CORPUS_DIR / "stats.json").write_text(text, encoding="utf-8")
        return 0
    if a.cmd == "tags":
        from corpus import REFS_DIR
        from corpus.tags import run as tag_run
        records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(REFS_DIR.glob("*.json"))]
        rows = tag_run(records)
        print(f"{len(rows)} rows, {sum(r['needsReview'] for r in rows)} need review")
        return 0
    if a.cmd == "accuracy":
        from corpus.accuracy import run
        s = run()
        print(json.dumps(s, indent=1))
        return 0
    if a.cmd == "accept":
        from pathlib import Path
        from corpus.assemble import accept
        bad = 0
        for d in a.drafts:
            ok, probs = accept(Path(d))
            print(("accepted " if ok else "REFUSED ") + d, *probs, sep="\n  ")
            bad += not ok
        return 1 if bad else 0
    if a.cmd == "queue":
        from corpus import queue as q
        items = q.seed() if a.action == "seed" else q.load()
        if a.action == "progress":
            print(json.dumps(q.progress(items), indent=1))
        elif a.action == "next":
            for i in q.pick_order(items, a.category)[: a.n]:
                print(i["id"], i["url"], "|", i["description"])
        else:
            print(f"{len(items)} queue items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
