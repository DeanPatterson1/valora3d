"""valora.ref/1: one structured record per studied clip (spec §9a + research/corpus/PILOT-NOTES.md §2).

validate(rec) -> list of problem strings; empty means valid. It never raises. The owner's sourcing
rules (spec §9a table) are checked here, so a record that breaks them cannot be accepted."""
import datetime
import math
import re
from urllib.parse import urlparse

from corpus import REF_SCHEMA

CATEGORIES = ("product", "furniture", "vehicle", "character", "abstract")
SIZE_CLASSES = ("macro", "hand", "furniture", "vehicle", "architectural")
ASPECTS = ("9:16", "16:9", "1:1", "4:5", "other")
CAMERA_MOVES = ("push", "pull", "orbit", "arc", "slide", "rise", "fall", "fpv", "handheld", "locked",
                "chase", "tilt", "pan", "other", "unclear")
LENS = ("ultrawide", "wide", "normal", "tele", "macro", "unclear")
HEIGHTS = ("ground", "low", "eye", "high", "overhead", "unclear")
FOCUS = ("deep", "shallow", "rack", "unclear")
SUBJECT_MOTION = ("static", "spin", "driving", "falling", "floating", "sim", "assembly", "other", "unclear")
RENDER_PASS = ("final", "clay", "viewport", "split", "unclear")
LAYOUTS = ("full", "split", "rotated", "blurred_fill", "letterbox", "other")
WORLDS = ("cyclorama", "interior", "street", "city", "highway", "nature", "abstract", "water", "space",
          "tunnel", "other")
ENERGY = ("calm", "medium", "hype")
LEVEL = ("low", "mid", "high")
TRI = ("yes", "no", "unclear")
IMPERFECTIONS = ("motionBlur", "focusBreathing", "exposureAdaptation", "rollingShutter", "sensorNoise",
                 "microShake", "lensFlare", "lensDistortion", "chromaticAberration")
OVERLAYS = ("hook_text", "captions", "end_card", "watermark", "graphics", "logo")
SOURCE_KINDS = ("owner", "stock", "link", "own_render")
STOCK = ("pexels", "mixkit", "pixabay")
LINK = ("youtube", "vimeo")          # spec §9a: link-only sources
QUALITY = ("T1", "T2", "T3", "T4")
METHODS = ("local_frames", "in_player", "script_ground_truth")
TOP_KEYS = {"schema", "id", "source", "method", "qualityEstimate", "subject", "format", "layout", "shots",
            "world", "lighting", "grade", "effects", "simulation", "surfaceState", "secondarySubjects",
            "overlays", "transitions", "cameraImperfections", "pacing", "neverThoughtOf", "evidence",
            "confidence", "ab"}
SHOT_KEYS = {"startS", "endS", "cameraMove", "lensClass", "cameraHeight", "dutchTilt", "focus",
             "subjectMotion", "renderPass", "notes"}
# Hosts each platform's pages live on (spec §9a): a record's url and a stock licence url must be on them.
PLATFORM_DOMAINS = {"pexels": ("pexels.com",), "mixkit": ("mixkit.co",), "pixabay": ("pixabay.com",),
                    "youtube": ("youtube.com", "youtu.be"), "vimeo": ("vimeo.com",)}
# Owner clips are the pilot (assets-in/refs/MANIFEST.md) or files the owner put in assets-in/refs/.
OWNER_PLATFORM = "owner-refs"
OWNER_FILE_PREFIX = "assets-in/refs/"
_PILOT_ID = re.compile(r"^ref\d{2}$")
_TIMESTAMP = re.compile(r"^t=\d+(?:\.\d+)?s$")
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
TILE_TOL_S, END_TOL_S = 0.05, 0.1


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _enum(out, path, v, allowed):
    if v not in allowed:
        out.append(f"{path}: {v!r} not in {list(allowed)}")


def _strlist(out, path, v):
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        out.append(f"{path}: must be a list of strings")


def iso_date(v):
    try:
        return isinstance(v, str) and datetime.date.fromisoformat(v).isoformat() == v
    except ValueError:
        return False


def on_platform(url, platform):
    """True when url is https on one of the platform's hosts (or a subdomain of one)."""
    u = urlparse(str(url or ""))
    host = (u.hostname or "").lower()
    return u.scheme == "https" and any(host == d or host.endswith("." + d)
                                       for d in PLATFORM_DOMAINS.get(platform, ()))


def licence_problems(lic, platform):
    """Problems with a stock clip's licence line, as read on the clip's own page. [] = fine."""
    if not (isinstance(lic, dict) and isinstance(lic.get("name"), str) and lic["name"].strip()
            and isinstance(lic.get("url"), str) and isinstance(lic.get("restricted"), bool)):
        return ["source.licence: {name, url, checkedAt, restricted} is required for stock clips"]
    out = []
    if not on_platform(lic["url"], platform):
        out.append(f"source.licence.url: must be an https page on {platform}'s own domain")
    if not iso_date(lic.get("checkedAt")):
        out.append("source.licence.checkedAt: the ISO date (YYYY-MM-DD) the licence line was read")
    if "restricted" in lic["name"].lower() and lic["restricted"] is not True:
        out.append("source.licence.restricted: a licence named 'restricted' must set restricted: true")
    return out




def _owner(out, rec_id, src):
    """Owner clips come only from the pilot or assets-in/refs/: never a URL or a public platform."""
    if src.get("platform") != OWNER_PLATFORM:
        out.append(f"source.platform: owner records are '{OWNER_PLATFORM}' (assets-in/refs), not a public platform")
    if src.get("url") is not None:
        out.append("source.url: owner records carry no url (a clip found online is a link or stock record)")
    f = src.get("file")
    if f is None:
        if not (isinstance(rec_id, str) and _PILOT_ID.match(rec_id)):
            out.append(f"source.file: an owner record that is not a pilot refNN names its file under {OWNER_FILE_PREFIX}")
    elif not (isinstance(f, str) and f.startswith(OWNER_FILE_PREFIX) and ".." not in f):
        out.append(f"source.file: owner files live under {OWNER_FILE_PREFIX}")


def _source(out, src, method, rec_id=None):
    if not isinstance(src, dict):
        out.append("source: must be an object")
        return
    kind, dl = src.get("kind"), src.get("downloaded")
    _enum(out, "source.kind", kind, SOURCE_KINDS)
    if not isinstance(dl, bool):
        out.append("source.downloaded: must be true or false")
    if src.get("selection") != "hand":
        out.append("source.selection: must be 'hand' (clips are hand-picked, never bulk; spec §9a)")
    if not isinstance(src.get("studiedAt"), str):
        out.append("source.studiedAt: the date the clip was studied")
    elif method == "in_player" and not iso_date(src["studiedAt"]):
        out.append("source.studiedAt: the ISO date (YYYY-MM-DD); in-player study is capped per day")
    if kind in ("link", "stock") and src.get("platform") in PLATFORM_DOMAINS and not on_platform(
            src.get("url"), src["platform"]):
        out.append(f"source.url: host must be on {src['platform']} ({', '.join(PLATFORM_DOMAINS[src['platform']])})")
    if kind in ("link", "stock") and dl and not isinstance(src.get("localFile"), str):
        out.append("source.localFile: a downloaded clip names its file under research/corpus/local/")
    if kind == "owner":
        _owner(out, rec_id, src)
    if kind == "link":
        _enum(out, "source.platform", src.get("platform"), LINK)
        if dl and not (src.get("platform") == "vimeo" and src.get("vimeoDownloadEnabled") is True):
            out.append("source.downloaded: link clips are never downloaded "
                       "(Vimeo only when the creator enabled download)")
        ts = src.get("timestampsS")
        if not (isinstance(ts, list) and len(ts) == 2 and all(_num(x) for x in ts) and 0 <= ts[0] < ts[1]):
            out.append("source.timestampsS: [startS, endS] of the studied span")
    elif kind == "stock":
        _enum(out, "source.platform", src.get("platform"), STOCK)
        lic = src.get("licence")
        lp = licence_problems(lic, src.get("platform"))
        out += lp
        if not lp and lic["restricted"] and dl:
            out.append("source.downloaded: a restricted-licence stock clip is studied in the player only")
        if dl and src.get("downloadedBy") != "owner":
            out.append("source.downloadedBy: stock files are downloaded by the owner's own click "
                       "(no automated collection)")
    elif kind == "own_render":
        if not isinstance(src.get("script"), str):
            out.append("source.script: an own render cites the pair definition it came from")
        if method != "script_ground_truth":
            out.append("method: own renders are recorded from the script (script_ground_truth)")
    if method == "local_frames" and not (dl or kind in ("owner", "own_render")):
        out.append("method: local_frames needs a local file (downloaded, owner-supplied or our render)")


def _format_and_shots(out, fmt, shots):
    if not isinstance(fmt, dict) or not isinstance(shots, list) or not shots:
        out.append("format/shots: format must be an object and shots a non-empty list")
        return
    _enum(out, "format.aspect", fmt.get("aspect"), ASPECTS)
    dur = fmt.get("durationS")
    if not _num(dur) or dur <= 0:
        out.append("format.durationS: a positive number")
        return
    if fmt.get("fps") is not None and not _num(fmt.get("fps")):
        out.append("format.fps: a number or null (unknown in the player)")
    if fmt.get("shotCount") != len(shots):
        out.append(f"format.shotCount: {fmt.get('shotCount')!r} but {len(shots)} shots")
    for i, sh in enumerate(shots):
        p = f"shots[{i}]"
        if not isinstance(sh, dict) or set(sh) - SHOT_KEYS or not _num(sh.get("startS")) or not _num(sh.get("endS")):
            out.append(f"{p}: needs numeric startS/endS and only keys {sorted(SHOT_KEYS)}")
            return
        _enum(out, f"{p}.cameraMove", sh.get("cameraMove"), CAMERA_MOVES)
        _enum(out, f"{p}.lensClass", sh.get("lensClass"), LENS)
        _enum(out, f"{p}.cameraHeight", sh.get("cameraHeight"), HEIGHTS)
        _enum(out, f"{p}.focus", sh.get("focus"), FOCUS)
        _enum(out, f"{p}.subjectMotion", sh.get("subjectMotion"), SUBJECT_MOTION)
        _enum(out, f"{p}.renderPass", sh.get("renderPass"), RENDER_PASS)
        if not isinstance(sh.get("dutchTilt"), bool):
            out.append(f"{p}.dutchTilt: true or false")
    if abs(shots[0]["startS"]) > TILE_TOL_S or abs(shots[-1]["endS"] - dur) > END_TOL_S or any(
            abs(a["endS"] - b["startS"]) > TILE_TOL_S for a, b in zip(shots, shots[1:])):
        out.append("shots: must be contiguous from 0 to format.durationS")
    cuts = fmt.get("cutTimesS")
    want = [sh["startS"] for sh in shots[1:]]
    if (not isinstance(cuts, list) or len(cuts) != len(want)
            or any(not _num(c) or abs(c - w) > TILE_TOL_S for c, w in zip(cuts, want))):
        out.append("format.cutTimesS: must equal the start of every shot after the first")


def _evidence(out, rec):
    ev = rec.get("evidence")
    if not isinstance(ev, dict) or not all(isinstance(v, list) and v and all(isinstance(x, str) for x in v)
                                           for v in ev.values()):
        out.append("evidence: {fieldPath: [timestamps or frame ids]} with non-empty lists")
        return
    need = []
    if isinstance(rec.get("shots"), list) and len(rec["shots"]) > 1 and rec.get("method") != "script_ground_truth":
        need.append("format.cutTimesS")
    if rec.get("method") != "script_ground_truth":
        need += [f"shots[{i}].cameraMove" for i, sh in enumerate(rec["shots"] if isinstance(rec.get("shots"), list) else [])
                 if isinstance(sh, dict) and sh.get("cameraMove") not in ("unclear", None)]
    if rec.get("method") == "in_player":
        bad = sorted({x for v in ev.values() for x in v if not _TIMESTAMP.match(x)})
        if bad:
            out.append(f"evidence: in_player evidence is timestamps like 't=4.2s' only (no frame files): {bad[:3]}")
    missing = [k for k in need if k not in ev]
    if missing:
        out.append(f"evidence: missing {missing} (PILOT-NOTES §1: cite frames or timestamps)")


def validate(rec):
    out = []
    if not isinstance(rec, dict):
        return ["record: must be a JSON object"]
    extra = sorted(set(rec) - TOP_KEYS)
    if extra:
        out.append(f"record: unknown keys {extra}")
    if rec.get("schema") != REF_SCHEMA:
        out.append(f"schema: must be {REF_SCHEMA}")
    if not isinstance(rec.get("id"), str) or not _ID.match(rec["id"]):
        out.append("id: lowercase letters, digits and '-' (2-41 chars)")
    _enum(out, "method", rec.get("method"), METHODS)
    _source(out, rec.get("source"), rec.get("method"), rec.get("id"))
    if rec.get("qualityEstimate") is not None:
        _enum(out, "qualityEstimate", rec.get("qualityEstimate"), QUALITY)
    subj = rec.get("subject") if isinstance(rec.get("subject"), dict) else {}
    _enum(out, "subject.category", subj.get("category"), CATEGORIES)
    _enum(out, "subject.sizeClass", subj.get("sizeClass"), SIZE_CLASSES)
    _format_and_shots(out, rec.get("format"), rec.get("shots"))
    lay = rec.get("layout") if isinstance(rec.get("layout"), dict) else {}
    _enum(out, "layout.kind", lay.get("kind"), LAYOUTS)
    _enum(out, "layout.contentAspect", lay.get("contentAspect"), ASPECTS)
    world = rec.get("world") if isinstance(rec.get("world"), dict) else {}
    _enum(out, "world.type", world.get("type"), WORLDS)
    _strlist(out, "world.atmosphere", world.get("atmosphere"))
    light = rec.get("lighting") if isinstance(rec.get("lighting"), dict) else {}
    _strlist(out, "lighting.setup", light.get("setup"))
    grade = rec.get("grade") if isinstance(rec.get("grade"), dict) else {}
    _enum(out, "grade.contrast", grade.get("contrast"), LEVEL)
    _enum(out, "grade.saturation", grade.get("saturation"), LEVEL)
    for k in ("effects", "simulation", "surfaceState", "secondarySubjects", "neverThoughtOf"):
        _strlist(out, k, rec.get(k))
    ov = rec.get("overlays")
    if not isinstance(ov, list) or any(x not in OVERLAYS for x in ov):
        out.append(f"overlays: a list drawn from {list(OVERLAYS)}")
    tr = rec.get("transitions")
    if not isinstance(tr, list) or any(not isinstance(t, dict) or not _num(t.get("atS"))
                                       or not isinstance(t.get("kind"), str) for t in tr):
        out.append("transitions: a list of {atS, kind}")
    imp = rec.get("cameraImperfections")
    if not isinstance(imp, dict) or set(imp) != set(IMPERFECTIONS) or any(v not in TRI for v in imp.values()):
        out.append(f"cameraImperfections: every key of {list(IMPERFECTIONS)} with yes/no/unclear")
    pac = rec.get("pacing") if isinstance(rec.get("pacing"), dict) else {}
    _enum(out, "pacing.energy", pac.get("energy"), ENERGY)
    if not (pac.get("musicSyncCuts") is None or isinstance(pac.get("musicSyncCuts"), bool)):
        out.append("pacing.musicSyncCuts: true, false or null")
    conf = rec.get("confidence") if isinstance(rec.get("confidence"), dict) else {}
    _enum(out, "confidence.overall", conf.get("overall"), LEVEL)
    _strlist(out, "confidence.uncertainFields", conf.get("uncertainFields"))
    src = rec.get("source") if isinstance(rec.get("source"), dict) else {}
    if src.get("kind") == "own_render" and not isinstance(rec.get("ab"), dict):
        out.append("ab: own renders carry {pair, param, a, b, frames, finding}")
    _evidence(out, rec)
    return out
