"""py -m corpus queue seed | queue progress | queue next --category C [--n N]"""
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
    a = ap.parse_args(argv)
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
