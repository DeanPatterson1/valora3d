"""py -m harness run --suite v0 [--models a,b] [--scripts x,y] [--tier keyframes|preview]
                       [--key-limit N] [--frames key|all] [--encode] [--run-id ID]"""
import argparse
import sys


def _csv(v):
    return [x.strip() for x in v.split(",") if x.strip()] if v else None


def main(argv=None):
    ap = argparse.ArgumentParser(prog="harness")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--suite", default="v0")
    r.add_argument("--models")
    r.add_argument("--scripts")
    r.add_argument("--tier", default="preview", choices=["keyframes", "preview"])
    r.add_argument("--key-limit", type=int)
    r.add_argument("--frames", default="key", choices=["key", "all"])
    r.add_argument("--encode", action="store_true")
    r.add_argument("--run-id")
    r.add_argument("--out-root", default="harness/out")
    a = ap.parse_args(argv)
    from harness.run import run_suite
    s = run_suite(a.suite, models=_csv(a.models), scripts=_csv(a.scripts), tier=a.tier, key_limit=a.key_limit,
                  out_root=a.out_root, run_id=a.run_id, encode=a.encode, frames=a.frames)
    for c in s["cases"]:
        print(c["case"], "ERROR " + c["error"].splitlines()[0] if c.get("error") else
              f"{c['tier']}{' (provisional)' if c['provisional'] else ''}")
    return 1 if any(c.get("error") for c in s["cases"]) else 0


if __name__ == "__main__":
    sys.exit(main())
