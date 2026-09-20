"""Validated render jobs and a durable, single-worker local queue."""
from __future__ import annotations

import base64
import binascii
from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import shutil
import struct
import threading
import uuid


MAX_BODY_BYTES = 128 * 1024 * 1024
MAX_PENDING_JOBS = 8
TERMINAL = frozenset({"done", "failed", "cancelled"})
ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,159}$")
JOB_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
# "watermark" is server-authoritative: canonical_settings() overwrites whatever
# the client sent, so a free preview always ships marked (watermark.py).
PRESETS = {
    "smoke": {"watermark": True, "engine": "EEVEE", "resolution": [320, 180], "duration_s": 1, "fps": 12, "samples": 8, "previewPrice": 0},
    "draft": {"watermark": True, "engine": "EEVEE", "resolution": [1280, 720], "duration_s": 6, "fps": 30, "samples": 32, "previewPrice": 0},
    "film_preview": {"watermark": True, "engine": "CYCLES", "resolution": [1280, 720], "duration_s": 10, "fps": 24, "samples": 96, "previewPrice": 0},
    "film_final": {"watermark": False, "engine": "CYCLES", "resolution": [1920, 1080], "duration_s": 10, "fps": 24, "samples": 192, "previewPrice": 0},
    "standard": {"watermark": False, "engine": "CYCLES", "resolution": [1920, 1080], "duration_s": 10, "fps": 30, "samples": 256, "previewPrice": 5},
    "cinematic": {"watermark": False, "engine": "CYCLES", "resolution": [1920, 1080], "duration_s": 15, "fps": 30, "samples": 512, "previewPrice": 8},
    "4k": {"watermark": False, "engine": "CYCLES", "resolution": [3840, 2160], "duration_s": 10, "fps": 30, "samples": 256, "previewPrice": 15},
}
SCENES = [
    {"id": "rainy_courtyard", "name": "After the Rain", "description": "Shaped reflections, falling rain and rippling wet pavement. Chosen whenever the scene plan asks for rain.", "aspects": ["16:9", "9:16"]},
    {"id": "turntable", "name": "Studio Turntable", "description": "A clean studio with four softboxes. The default for a dry, daylight scene.", "aspects": ["16:9", "9:16"]},
    {"id": "night_garage", "name": "Night Garage", "description": "Dramatic garage lighting. Chosen for a dry night scene.", "aspects": ["16:9", "9:16"]},
]
SCENE_IDS = {scene["id"] for scene in SCENES}
SPEC_FIELDS = frozenset({"schema", "jobId", "buildId", "car", "parts", "paint", "tint", "ride_height", "scene", "preset", "aspect", "duration_s", "fps", "resolution", "samples", "engine", "frame_start", "frame_end", "total_frames", "hide_logos", "spec", "plan", "camera_programme"})

# The studio's ScenePlan owns the output settings, so a preset no longer fixes the
# duration. It still fixes the quality ladder (engine, samples, watermark) and now
# caps the frame count, which is what actually costs GPU time.
MAX_FRAMES = {"smoke": 24, "draft": 300, "film_preview": 450, "film_final": 900, "standard": 900, "cinematic": 900, "4k": 450}

RESOLUTIONS = {"720p": [1280, 720], "1080p": [1920, 1080], "1440p": [2560, 1440], "4k": [3840, 2160]}
ALLOWED_FPS = (24, 30, 60)
ALLOWED_DURATIONS = (5, 10, 15, 30)
SHOT_ACTIONS = ("slow_orbit", "hero_push_in", "low_tracking", "handheld_walk_toward")


def _number(value, low, high, name):
    if type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(value) or not low <= value <= high:
        raise JobError(f"plan.{name} is out of range.")
    return float(value)


def validate_plan(plan):
    """Mirror of `ScenePlanSchema`, for the fields the renderer actually reads.

    The plan drives a Blender render loop, so it is checked here rather than trusted:
    the browser is not the only thing that can reach this port.
    """
    if not isinstance(plan, dict):
        raise JobError("plan must be an object.")
    for group in ("camera", "lighting", "effects", "shots", "output"):
        if group not in plan:
            raise JobError(f"plan.{group} is required.")

    camera = plan["camera"]
    if not isinstance(camera, dict):
        raise JobError("plan.camera must be an object.")
    _number(camera.get("lensMm"), 18, 135, "camera.lensMm")
    _number(camera.get("heightM"), 0.2, 3, "camera.heightM")
    _number(camera.get("motionStrength"), 0, 1, "camera.motionStrength")

    lighting = plan["lighting"]
    if not isinstance(lighting, dict):
        raise JobError("plan.lighting must be an object.")
    # Applied straight to Blender's exposure, in stops.
    _number(lighting.get("exposure"), -3, 3, "lighting.exposure")

    effects = plan["effects"]
    if not isinstance(effects, dict):
        raise JobError("plan.effects must be an object.")
    for name in ("rain", "wetGround", "motionBlur", "depthOfField"):
        _number(effects.get(name), 0, 1, f"effects.{name}")

    output = plan["output"]
    if not isinstance(output, dict):
        raise JobError("plan.output must be an object.")
    if output.get("resolution") not in RESOLUTIONS:
        raise JobError("plan.output.resolution is not a supported size.")
    if output.get("fps") not in ALLOWED_FPS:
        raise JobError("plan.output.fps must be 24, 30 or 60.")
    if output.get("durationS") not in ALLOWED_DURATIONS:
        raise JobError("plan.output.durationS must be 5, 10, 15 or 30.")

    shots = plan["shots"]
    if not isinstance(shots, list) or not 1 <= len(shots) <= 2:
        raise JobError("plan.shots must hold one or two shots.")
    cursor = 0.0
    for shot in shots:
        if not isinstance(shot, dict) or shot.get("action") not in SHOT_ACTIONS:
            raise JobError("plan.shots has an unknown shot action.")
        start = _number(shot.get("start"), 0, 600, "shots[].start")
        end = _number(shot.get("end"), 0, 600, "shots[].end")
        _number(shot.get("distanceMultiplier"), 0.4, 2.5, "shots[].distanceMultiplier")
        # Contiguity is the viewer's invariant; a gap would freeze the camera mid-video.
        if abs(start - cursor) > 1e-6 or end <= start:
            raise JobError("plan.shots must be contiguous and run forwards.")
        cursor = end
    if abs(cursor - output["durationS"]) > 1e-6:
        raise JobError("plan.shots must end at plan.output.durationS.")
    return plan


class JobError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def canonical_settings(preset, scene, aspect, plan=None):
    if not isinstance(preset, str) or preset not in PRESETS:
        raise JobError("Unknown render preset.")
    if not isinstance(scene, str) or scene not in SCENE_IDS:
        raise JobError("Unknown render scene.")
    if aspect not in ("16:9", "9:16"):
        raise JobError("Aspect must be 16:9 or 9:16.")
    values = deepcopy(PRESETS[preset])
    values.pop("previewPrice")
    if plan is not None:
        output = plan["output"]
        wanted = list(RESOLUTIONS[output["resolution"]])
        # A preview is a cheaper look at the same shot, so it never renders larger
        # than its tier: at full resolution it would cost what the final costs.
        preview = values["watermark"]
        tier = values["resolution"]
        values["resolution"] = tier if preview and wanted[0] * wanted[1] > tier[0] * tier[1] else wanted
        values["fps"] = output["fps"]
        values["duration_s"] = output["durationS"]
    if aspect == "9:16":
        values["resolution"].reverse()
    frames = values["duration_s"] * values["fps"]
    if frames > MAX_FRAMES[preset]:
        raise JobError(f"{frames} frames is past this quality's limit of {MAX_FRAMES[preset]}. Shorten the shot or lower the frame rate.")
    return {**values, "frame_start": 1, "frame_end": frames, "total_frames": frames}


def validate_job(payload):
    if not isinstance(payload, dict) or set(payload) != {"job", "snapshot"}:
        raise JobError("Expected a JSON object containing job and snapshot.")
    job = payload["job"]
    if not isinstance(job, dict) or type(job.get("schema")) is not int or job["schema"] != 1:
        raise JobError("Render job schema must be 1.")
    if set(job) - SPEC_FIELDS:
        raise JobError("Unsupported job fields: " + ", ".join(sorted(set(job) - SPEC_FIELDS)))
    for name in ("car", "buildId"):
        value = job.get(name)
        if name == "buildId" and value is None:
            continue
        if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
            raise JobError(f"{name} must be an identifier, not a file path.")
    parts = job.get("parts", [])
    if not isinstance(parts, list) or len(parts) > 256 or any(not isinstance(value, str) or not ID_PATTERN.fullmatch(value) for value in parts):
        raise JobError("parts must contain at most 256 part identifiers.")
    paint = job.get("paint", {"hex": "#ffffff", "finish": "gloss"})
    if not isinstance(paint, dict) or set(paint) - {"hex", "finish"} or not isinstance(paint.get("hex"), str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", paint["hex"]):
        raise JobError("paint.hex must be a six-digit hex color.")
    if paint.get("finish", "gloss") not in ("stock", "solid", "gloss", "matte", "metallic", "satin", "frozen", "chrome", "pearlescent"):
        raise JobError("Unsupported paint finish.")
    for key, lower, upper in (("tint", 0, 1), ("ride_height", -1, 1)):
        value = job.get(key, 0)
        if type(value) not in (int, float) or not math.isfinite(value) or not lower <= value <= upper:
            raise JobError(f"{key} is out of range.")
    if "hide_logos" in job and type(job["hide_logos"]) is not bool:
        raise JobError("hide_logos must be true or false.")
    if job.get("camera_programme", "film") not in ("film", "plan"):
        raise JobError("camera_programme must be film or plan.")
    plan = validate_plan(job["plan"]) if "plan" in job else None
    settings = canonical_settings(job.get("preset"), job.get("scene"), job.get("aspect", "16:9"), plan)
    for key, value in settings.items():
        if key in job and (job[key] != value or type(job[key]) is not type(value) or (key == "resolution" and any(type(number) is not int for number in job[key]))):
            raise JobError(f"{key} must match the selected preset and aspect.")
    import spec as render_spec
    document = None      # a spec-less job carries no `look`/`grain` key; pipeline keeps grain rain-scoped
    if "spec" in job:
        try:
            document = render_spec.validate_spec(job["spec"])
        except render_spec.SpecError as exc:
            raise JobError("spec: " + str(exc)) from exc
        if document["scene"] != job.get("scene"):
            raise JobError("spec.scene must match the job scene.")
        look = render_spec.spec_to_look(document)
        grain = document["look"]["grain"]
    canonical = {**job, **settings, "aspect": job.get("aspect", "16:9"), "parts": list(parts), "paint": {"hex": paint["hex"], "finish": paint.get("finish", "gloss")}}
    if document is not None:
        canonical["spec"], canonical["look"], canonical["grain"] = document, look, grain
    canonical.pop("jobId", None)
    encoded = payload["snapshot"]
    if not isinstance(encoded, str) or not encoded or len(encoded) > MAX_BODY_BYTES:
        raise JobError("snapshot must be a base64 GLB file.")
    try:
        snapshot = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise JobError("snapshot is not valid base64.") from exc
    validate_snapshot(snapshot)
    return canonical, snapshot


def validate_snapshot(snapshot):
    if len(snapshot) < 20 or snapshot[:4] != b"glTF":
        raise JobError("snapshot must be a binary glTF (GLB) file.")
    version, declared_length, json_length, chunk_type = struct.unpack_from("<IIII", snapshot, 4)
    if version != 2 or declared_length != len(snapshot) or chunk_type != 0x4E4F534A or json_length % 4 or 20 + json_length > len(snapshot):
        raise JobError("snapshot has an invalid GLB header or length.")
    try:
        document = json.loads(snapshot[20:20 + json_length])
    except (ValueError, UnicodeDecodeError) as exc:
        raise JobError("snapshot has invalid glTF JSON.") from exc
    if not isinstance(document, dict) or not isinstance(document.get("asset"), dict) or document["asset"].get("version") != "2.0":
        raise JobError("snapshot must contain a glTF 2.0 asset.")
    for field in ("buffers", "images"):
        resources = document.get(field, [])
        if not isinstance(resources, list):
            raise JobError("snapshot resources must be embedded.")
        for resource in resources:
            if not isinstance(resource, dict):
                raise JobError("snapshot resources must be embedded.")
            uri = resource.get("uri")
            if uri is not None and (not isinstance(uri, str) or not uri.startswith("data:")):
                raise JobError("snapshot cannot reference external files or URLs.")
    cursor = 20 + json_length
    while cursor < len(snapshot):
        if cursor + 8 > len(snapshot):
            raise JobError("snapshot contains an incomplete GLB chunk.")
        chunk_length = struct.unpack_from("<I", snapshot, cursor)[0]
        if chunk_length % 4 or cursor + 8 + chunk_length > len(snapshot):
            raise JobError("snapshot contains an invalid GLB chunk length.")
        cursor += 8 + chunk_length


class JobStore:
    def __init__(self, root: Path, pipeline, max_pending=MAX_PENDING_JOBS, start_worker=True):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.pipeline = pipeline
        self.max_pending = max_pending
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        self.jobs = {}
        self.pending = deque()
        self.active_id = None
        self.cancel_events = {}
        self.stopping = False
        self.worker = None
        self._restore()
        if start_worker:
            self.worker = threading.Thread(target=self._work, name="render-worker", daemon=True)
            self.worker.start()

    def directory(self, job_id):
        if not isinstance(job_id, str) or not JOB_ID_PATTERN.fullmatch(job_id):
            raise JobError("Job not found.", 404)
        path = (self.root / job_id).resolve()
        if path.parent != self.root or path != self.root / job_id:
            raise JobError("Invalid job directory.", 400)
        return path

    def _restore(self):
        for folder in self.root.iterdir():
            if not JOB_ID_PATTERN.fullmatch(folder.name) or not folder.is_dir() or folder.resolve().parent != self.root:
                continue
            try:
                item = json.loads((folder / "job.json").read_text(encoding="utf-8"))
                if not isinstance(item, dict) or item.get("jobId") != folder.name or not isinstance(item.get("job"), dict):
                    continue
                self.jobs[folder.name] = item
                if item.get("status") == "queued" and (folder / "snapshot.glb").is_file():
                    self.pending.append(folder.name)
                elif item.get("status") not in TERMINAL:
                    item.update(status="failed", error="The render service stopped before this job finished.", updatedAt=now())
                    self._persist(item)
            except (OSError, ValueError, TypeError):
                continue
        self.pending = deque(sorted(self.pending, key=lambda key: self.jobs[key].get("createdAt", "")))

    def _persist(self, item):
        path = self.directory(item["jobId"]) / "job.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    def _update(self, job_id, **updates):
        item = self.jobs[job_id]
        item.update(updates, updatedAt=now(), revision=item.get("revision", 0) + 1)
        self._persist(item)
        self.changed.notify_all()

    def _public(self, item):
        result = deepcopy(item)
        queued_ids = [key for key in self.pending if self.jobs.get(key, {}).get("status") == "queued"]
        result["position"] = queued_ids.index(item["jobId"]) + 1 if item["jobId"] in queued_ids else 0
        result["output"] = {}
        folder = self.directory(item["jobId"])
        for key, filename in (("latest", "latest.jpg"), ("video", "video.mp4"), ("poster", "poster.jpg")):
            if (key == "latest" or item["status"] == "done") and (folder / filename).is_file():
                result["output"][key] = f"/files/{item['jobId']}/{filename}"
        return result

    def submit(self, spec, snapshot):
        with self.changed:
            if self.stopping:
                raise JobError("The render service is shutting down.", 503)
            if sum(item["status"] not in TERMINAL for item in self.jobs.values()) >= self.max_pending:
                raise JobError("The local queue is full. Wait for a render to finish.", 429)
            job_id = uuid.uuid4().hex
            folder = self.directory(job_id)
            folder.mkdir()
            (folder / "snapshot.glb").write_bytes(snapshot)
            timestamp = now()
            item = {"jobId": job_id, "job": {**deepcopy(spec), "jobId": job_id}, "status": "queued", "progress": 0, "frame": 0, "totalFrames": spec["total_frames"], "createdAt": timestamp, "updatedAt": timestamp, "revision": 1}
            self.jobs[job_id] = item
            self._persist(item)
            self.pending.append(job_id)
            self.changed.notify_all()
            return self._public(item)

    def get(self, job_id):
        with self.lock:
            self.directory(job_id)
            if job_id not in self.jobs:
                raise JobError("Job not found.", 404)
            return self._public(self.jobs[job_id])

    def list(self):
        with self.lock:
            return [self._public(item) for item in sorted(self.jobs.values(), key=lambda item: item["createdAt"], reverse=True)]

    def queue_length(self):
        with self.lock:
            return sum(item["status"] not in TERMINAL for item in self.jobs.values())

    def cancel(self, job_id):
        with self.changed:
            item = self.get(job_id)
            if item["status"] in TERMINAL:
                return item
            if job_id in self.cancel_events:
                self.cancel_events[job_id].set()
            self._update(job_id, status="cancelled")
            return self.get(job_id)

    def delete(self, job_id):
        with self.changed:
            item = self.get(job_id)
            if item["status"] not in TERMINAL or self.active_id == job_id:
                raise JobError("Wait for the render process to stop before deleting this job.", 409)
            folder = self.directory(job_id)
            shutil.rmtree(folder)
            del self.jobs[job_id]
            self.pending = deque(key for key in self.pending if key != job_id)
            self.changed.notify_all()

    def retry(self, job_id):
        with self.changed:
            item = self.get(job_id)
            if item["status"] not in {"failed", "cancelled"} or self.active_id == job_id:
                raise JobError("Only a stopped failed or cancelled render can be retried.", 409)
            try:
                snapshot = (self.directory(job_id) / "snapshot.glb").read_bytes()
            except OSError as exc:
                raise JobError("This render no longer has its saved snapshot.", 409) from exc
            validate_snapshot(snapshot)
            return self.submit(item["job"], snapshot)

    def estimate(self, preset, scene, aspect, plan=None):
        settings = canonical_settings(preset, scene, aspect, plan)
        with self.lock:
            measurements = [item.get("stats", {}).get("secondsPerFrame") for item in self.jobs.values() if item["status"] == "done" and item["job"].get("preset") == preset]
        measurements = [value for value in measurements if type(value) in (int, float) and math.isfinite(value) and value > 0]
        seconds_per_frame = sum(measurements) / len(measurements) if measurements else {"smoke": 0.5, "draft": 0.8, "film_preview": 7, "film_final": 18, "standard": 20, "cinematic": 30, "4k": 50}[preset]
        seconds = round(120 + settings["total_frames"] * seconds_per_frame)
        return {"seconds": seconds, "estimatedSeconds": seconds, "frames": settings["total_frames"], "previewPrice": PRESETS[preset]["previewPrice"], "currency": "USD", "measured": bool(measurements), "preset": preset, "scene": scene, "aspect": aspect}

    def _work(self):
        while True:
            with self.changed:
                self.changed.wait_for(lambda: self.stopping or bool(self.pending))
                if self.stopping:
                    return
                job_id = self.pending.popleft()
                if self.jobs.get(job_id, {}).get("status") != "queued":
                    continue
                self.active_id = job_id
                cancelled = threading.Event()
                self.cancel_events[job_id] = cancelled
                self._update(job_id, status="preparing", progress=0.01)
                spec = deepcopy(self.jobs[job_id]["job"])

            def progress(update):
                with self.changed:
                    if cancelled.is_set() or self.jobs[job_id]["status"] in TERMINAL:
                        return
                    fields = {key: value for key, value in update.items() if key in {"status", "progress", "frame", "totalFrames", "message", "secondsRemaining", "remainingSeconds"}}
                    if "secondsRemaining" in fields:
                        fields["remainingSeconds"] = fields["secondsRemaining"]
                    if fields.get("status") not in {None, "preparing", "rendering", "encoding"}:
                        fields.pop("status")
                    if "progress" in fields:
                        fields["progress"] = max(0, min(0.99, float(fields["progress"])))
                    self._update(job_id, **fields)

            try:
                stats = self.pipeline(spec, self.directory(job_id), progress, cancelled)
                with self.changed:
                    if not cancelled.is_set() and self.jobs[job_id]["status"] != "cancelled":
                        if not (self.directory(job_id) / "video.mp4").is_file():
                            raise RuntimeError("The render finished without producing a video.")
                        self._update(job_id, status="done", progress=1, frame=spec["total_frames"], stats=stats or {})
            except Exception as exc:
                with self.changed:
                    if not cancelled.is_set() and self.jobs[job_id]["status"] != "cancelled":
                        self._update(job_id, status="failed", error=str(exc)[:2000] or type(exc).__name__)
            finally:
                with self.changed:
                    if cancelled.is_set() and self.jobs[job_id]["status"] != "cancelled":
                        self._update(job_id, status="cancelled")
                    self.cancel_events.pop(job_id, None)
                    self.active_id = None
                    self.changed.notify_all()

    def close(self):
        with self.changed:
            self.stopping = True
            for event in self.cancel_events.values():
                event.set()
            self.changed.notify_all()
        if self.worker:
            self.worker.join(timeout=10)
