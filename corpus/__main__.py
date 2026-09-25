"""py -m corpus queue seed | queue progress | queue next --category C [--n N] | accept DRAFT... | accuracy | tags | stats [--write]"""
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
    a = ap.parse_args(argv)
    if a.cmd == "stats":
        from corpus import CORPUS_DIR, REFS_DIR
        from corpus.stats import compute
        records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(REFS_DIR.glob("*.json"))]
        acc = CORPUS_DIR / "accuracy.json"
        trusted = set(json.loads(acc.read_text(encoding="utf-8"))["trusted"]) if acc.exists() else None
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
