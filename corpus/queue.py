"""Candidate queue for the corpus first cut (spec §9a): research/corpus/queue.jsonl, one object per
line, sorted by id. Nothing here fetches anything. Link candidates come from SOURCES.md rows; stock
candidates are nominated one URL at a time by whoever looked at that clip's page."""
import json
import re
from urllib.parse import urlparse

from corpus import CORPUS_DIR
from corpus.schema import PLATFORM_DOMAINS, STOCK, licence_problems, on_platform

QUEUE = CORPUS_DIR / "queue.jsonl"
STATUSES = ("candidate", "picked", "studied", "rejected")
REJECT_REASONS = ("dead_link", "not_cg", "ai_generated", "duplicate", "too_long", "login_wall",
                  "licence", "off_topic", "private")
# First cut ~100 records (spec §9a): 11 pilot + link + stock + own A/B pairs.
FIRST_CUT = {"link": {"product": 15, "furniture": 10, "vehicle": 13, "character": 10, "abstract": 12},
             "stock": {"product": 8, "furniture": 4, "vehicle": 3, "character": 1, "abstract": 4},
             "own_render": {"product": 5, "furniture": 2, "vehicle": 3, "character": 0, "abstract": 0}}
LINK_OK = ("youtube", "vimeo")
TOP_TIER = ("manvsmachine", "buck", "tendril", "holmedal", "wannerstedt", "mondlicht", "mackevision",
            "tax free", "superplastic", "lego")
STOCK_DOMAINS = {p: PLATFORM_DOMAINS[p][0] for p in STOCK}  # one host table: corpus.schema
# Stock clips are picked by the owner or a named person (spec §9a: no automated collection).
_PERSON = re.compile(r"^(?:owner|[A-Z][a-z]+(?: [A-Z][a-z'-]+){0,3})$")
_CAT = {"P": "product", "F": "furniture", "V": "vehicle", "C": "character", "A": "abstract"}
_PLATFORM = {"vimeo": "vimeo", "youtube": "youtube", "yt shorts": "youtube", "behance": "behance",
             "artstation": "artstation", "instagram": "instagram", "tiktok": "tiktok",
             "studio site": "studio_site", "motionographer": "motionographer"}
_ROW = re.compile(r"^\| ([PFVCA])(\d+) \| (\S+) \| ([^|]+?) \| ([^|]*?) \| (.+?) \|\s*$")
_VERT_RANK = {"y": 0, "y?": 0, "?": 1, "n": 2}


def parse_sources(text):
    items = []
    for line in text.splitlines():
        m = _ROW.match(line.strip())
        if not m:
            continue
        cat, num, url, platform, vert, desc = m.groups()
        items.append({"id": f"src-{cat.lower()}{num}", "kind": "link", "url": url,
                      "platform": _PLATFORM.get(platform.strip().lower(), "other"),
                      "category": _CAT[cat], "vertical": vert.strip() or "?",
                      "description": desc.strip(), "status": "candidate"})
    return items


def load(path=QUEUE):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def save(items, path=QUEUE):
    rows = sorted(items, key=lambda i: i["id"])
    path.write_text("".join(json.dumps(i, ensure_ascii=False, sort_keys=True) + "\n" for i in rows),
                    encoding="utf-8")


def seed(path=QUEUE, sources=CORPUS_DIR / "SOURCES.md"):
    """Merge SOURCES.md rows into the queue; existing statuses are kept."""
    items = {i["id"]: i for i in load(path)}
    for new in parse_sources(sources.read_text(encoding="utf-8")):
        items.setdefault(new["id"], new)
    save(list(items.values()), path)
    return list(items.values())


def _natural(i):
    m = re.match(r"^src-[a-z](\d+)$", i["id"])
    return (int(m.group(1)) if m else 0, i["id"])


def pick_order(items, category):
    """Link candidates in the order a person should study them: vertical first (the target format),
    then top-tier studios, then SOURCES order."""
    pool = [i for i in items if i["kind"] == "link" and i["status"] == "candidate"
            and i["platform"] in LINK_OK and i["category"] == category]
    top = lambda i: 0 if any(t in i["description"].lower() for t in TOP_TIER) else 1  # noqa: E731
    return sorted(pool, key=lambda i: (_VERT_RANK.get(i["vertical"], 1), top(i), _natural(i)))


def nominate_stock(items, *, platform, url, category, why, licence, picked_by):
    if platform not in STOCK_DOMAINS:
        raise ValueError(f"platform must be one of {list(STOCK_DOMAINS)}")
    if not on_platform(url, platform):
        raise ValueError(f"url is not on the {platform} domain")
    lp = licence_problems(licence, platform)
    if lp:
        raise ValueError("licence: " + "; ".join(lp))
    if not isinstance(picked_by, str) or not _PERSON.match(picked_by):
        raise ValueError("picked_by: 'owner' or the name of the person who looked at the clip's page")
    if any(i.get("url") == url for i in items):
        raise ValueError("duplicate url")
    if category not in _CAT.values():
        raise ValueError("bad category")
    slug = re.sub(r"[^a-z0-9]+", "-", urlparse(url).path.lower()).strip("-")[-30:]
    item = {"id": f"{platform}-{slug}", "kind": "stock", "url": url, "platform": platform,
            "category": category, "description": why, "licence": licence, "pickedBy": picked_by,
            "status": "picked"}
    items.append(item)
    return item


def set_status(items, qid, status, reason=None):
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    if status == "rejected" and reason not in REJECT_REASONS:
        raise ValueError(f"a rejection needs a reason from {REJECT_REASONS}")
    it = next((i for i in items if i["id"] == qid), None)
    if it is None:
        raise ValueError(f"no queue item {qid!r}")
    it["status"] = status
    if reason:
        it["reason"] = reason
    return it


def progress(items):
    out = {}
    for kind, targets in FIRST_CUT.items():
        out[kind] = {c: {"studied": sum(1 for i in items if i["kind"] == kind and i["category"] == c
                                        and i["status"] == "studied"), "target": t}
                     for c, t in targets.items()}
    return out
