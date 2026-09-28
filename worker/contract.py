"""The job contract: input validation and the error codes a failed job reports.

Input (RunPod `input`):
    {
      "job_id": "abc123",                      # the site's job id, [A-Za-z0-9_-]{1,64}
      "glb_url": "https://...",                # presigned R2 GET of the user's .glb
      "output_put_urls": {                     # presigned R2 PUTs; sign them with these Content-Types
        "video": "https://...",                # video/mp4        (required)
        "poster": "https://...",               # image/jpeg       (required)
        "frames_zip": "https://..."            # application/zip  (optional)
      },
      "params": {
        "prompt": "", "world": null, "aspect": "9:16", "tier": "preview", "seed": null,
        "duration": null, "paint": null, "finish": "gloss", "markers": []
      }
    }

Everything the engine validates more deeply (world ids, marker anchors, paint colour) is only shape-checked
here; the engine rejects the rest with exit 5, which maps to INPUT_REJECTED."""
import re
from dataclasses import dataclass, field

TIERS = ("preview", "final")
ASPECTS = ("9:16", "16:9")
FINISHES = ("gloss", "metallic", "satin", "matte")
OUTPUT_TYPES = {"video": "video/mp4", "poster": "image/jpeg", "frames_zip": "application/zip"}
REQUIRED_OUTPUTS = ("video", "poster")
MAX_PROMPT = 2000
MAX_MARKERS = 8          # engine/markers.py MAX_MARKERS
MAX_MARKER_TEXT = 280    # engine/markers.py MAX_TEXT
DURATION_RANGE = (3, 30)  # engine/script.py DURATION_RANGE (the site offers 8-12)
SEED_LIMIT = 2 ** 31      # engine/director/job.py SEED_LIMIT
_JOB_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_WORLD = re.compile(r"^[a-z0-9_]{1,64}$")
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

# code -> (retryable, user-safe message). Retryable = the same input may succeed on another attempt.
ERRORS = {
    "INVALID_INPUT": (False, "The render request was malformed."),
    "GLB_DOWNLOAD_FAILED": (True, "The model could not be downloaded."),
    "GLB_TOO_LARGE": (False, "The model is larger than the 200 MB limit."),
    "GLB_INVALID": (False, "The file is not a valid binary glTF (.glb) model."),
    "INPUT_REJECTED": (False, "The model or request was rejected by the renderer."),
    "RENDER_FAILED": (True, "The render failed."),
    "RENDER_TIMEOUT": (True, "The render took too long and was stopped."),
    "FRAMES_MISSING": (True, "The render finished without producing every frame."),
    "ENCODE_FAILED": (True, "The video could not be encoded."),
    "UPLOAD_FAILED": (True, "The result could not be uploaded."),
    "WORKER_MISCONFIGURED": (True, "The render worker is misconfigured."),
    "INTERNAL": (True, "The render worker hit an unexpected error."),
}


class WorkerError(Exception):
    """A job failure with a stable code. `detail` is for logs/operators; `message` is safe to show a user."""

    def __init__(self, code, detail=""):
        if code not in ERRORS:
            raise ValueError(f"unknown error code {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = str(detail)[:500]

    @property
    def retryable(self):
        return ERRORS[self.code][0]

    @property
    def message(self):
        return ERRORS[self.code][1]

    def to_dict(self):
        return {"code": self.code, "message": self.message, "detail": self.detail, "retryable": self.retryable}


@dataclass
class Params:
    prompt: str = ""
    world: str | None = None
    aspect: str | None = None
    tier: str = "preview"
    seed: int | None = None
    duration: float | None = None
    paint: str | None = None
    finish: str = "gloss"
    markers: list = field(default_factory=list)


@dataclass
class Job:
    job_id: str
    glb_url: str
    outputs: dict          # output name -> PUT url
    params: Params


def _bad(msg):
    raise WorkerError("INVALID_INPUT", msg)


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _markers(v):
    if v is None:
        return []
    if not isinstance(v, list):
        _bad("params.markers must be a list")
    if len(v) > MAX_MARKERS:
        _bad(f"params.markers: at most {MAX_MARKERS}")
    for i, m in enumerate(v):
        if not isinstance(m, dict) or not isinstance(m.get("anchor"), dict):
            _bad(f"params.markers[{i}] must be an object with an anchor")
        text = m.get("text", "")
        if not isinstance(text, str) or len(text) > MAX_MARKER_TEXT:
            _bad(f"params.markers[{i}].text must be a string of at most {MAX_MARKER_TEXT} characters")
    return v


def parse_params(p):
    if p is None:
        p = {}
    if not isinstance(p, dict):
        _bad("params must be an object")
    known = {"prompt", "world", "aspect", "tier", "seed", "duration", "paint", "finish", "markers"}
    extra = set(p) - known
    if extra:
        _bad(f"unknown params: {', '.join(sorted(extra))}")
    prompt = p.get("prompt") or ""
    if not isinstance(prompt, str) or len(prompt) > MAX_PROMPT or "\x00" in prompt:
        _bad(f"params.prompt must be text of at most {MAX_PROMPT} characters")
    world = p.get("world")
    if world is not None and (not isinstance(world, str) or not _WORLD.match(world)):
        _bad("params.world must be a world id")
    aspect = p.get("aspect")
    if aspect is not None and aspect not in ASPECTS:
        _bad(f"params.aspect must be one of {ASPECTS}")
    tier = p.get("tier") or "preview"
    if tier not in TIERS:
        _bad(f"params.tier must be one of {TIERS}")
    seed = p.get("seed")
    if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed < SEED_LIMIT):
        _bad(f"params.seed must be an integer from 0 to {SEED_LIMIT - 1}")
    duration = p.get("duration")
    if duration is not None and (not _num(duration) or not DURATION_RANGE[0] <= duration <= DURATION_RANGE[1]):
        _bad(f"params.duration must be {DURATION_RANGE[0]}-{DURATION_RANGE[1]} seconds")
    paint = p.get("paint")
    if paint is not None and (not isinstance(paint, str) or not _HEX.match(paint)):
        _bad("params.paint must be #rrggbb")
    finish = p.get("finish") or "gloss"
    if finish not in FINISHES:
        _bad(f"params.finish must be one of {FINISHES}")
    return Params(prompt=prompt, world=world, aspect=aspect, tier=tier, seed=seed,
                  duration=float(duration) if duration is not None else None, paint=paint, finish=finish,
                  markers=_markers(p.get("markers")))


def parse_job(inp):
    """RunPod `input` -> Job, or WorkerError(INVALID_INPUT). URLs are checked for scheme/host by transfer.py."""
    if not isinstance(inp, dict):
        _bad("input must be an object")
    job_id = inp.get("job_id")
    if not isinstance(job_id, str) or not _JOB_ID.match(job_id):
        _bad("job_id must match [A-Za-z0-9_-]{1,64}")
    glb_url = inp.get("glb_url")
    if not isinstance(glb_url, str) or not glb_url:
        _bad("glb_url is required")
    outs = inp.get("output_put_urls")
    if not isinstance(outs, dict):
        _bad("output_put_urls must be an object")
    unknown = set(outs) - set(OUTPUT_TYPES)
    if unknown:
        _bad(f"unknown outputs: {', '.join(sorted(unknown))}")
    for name in REQUIRED_OUTPUTS:
        if not isinstance(outs.get(name), str) or not outs[name]:
            _bad(f"output_put_urls.{name} is required")
    outputs = {k: v for k, v in outs.items() if v}
    if any(not isinstance(v, str) for v in outputs.values()):
        _bad("output_put_urls values must be URLs")
    return Job(job_id=job_id, glb_url=glb_url, outputs=outputs, params=parse_params(inp.get("params")))


def error_for_exit(code, last_error, stage=None):
    """site_job exit code + its last SITEJOB error text + the last stage it announced -> WorkerError.

    site_job exits 5 only for director/paint input errors; ingest's IngestRejected ("The model ...", "Only .glb
    ...") surfaces as exit 1 during the ingest stage, so an ingest-stage failure that is not a Blender crash is
    also the user's input."""
    text = last_error or f"site_job exited {code}"
    if code == 5:
        return WorkerError("INPUT_REJECTED", text)
    if code == 2:
        return WorkerError("WORKER_MISCONFIGURED", f"site_job usage error: {text}")
    if last_error and "timed out" in last_error.lower():
        return WorkerError("RENDER_TIMEOUT", text)
    if stage == "ingest" and last_error and not last_error.startswith("Blender"):
        return WorkerError("INPUT_REJECTED", text)
    return WorkerError("RENDER_FAILED", text)
