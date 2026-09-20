"""HTTP boundary and queue tests; uses no real renderer or GPU."""
import base64
from copy import deepcopy
import http.client
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import uuid

os.environ.setdefault("MV_RENDER_CAR_IDS", "*")

from jobs import JobError, JobStore, MAX_BODY_BYTES, PRESETS, canonical_settings, validate_job, validate_plan
from server import RenderServer, main


def glb(document=None):
    document = document or {"asset": {"version": "2.0"}}
    data = json.dumps(document).encode("utf-8")
    data += b" " * (-len(data) % 4)
    return struct.pack("<4sIIII", b"glTF", 2, len(data) + 20, len(data), 0x4E4F534A) + data


def payload():
    return {"job": {"schema": 1, "car": "bmw-m4-g82", "parts": [], "paint": {"hex": "#99aabb", "finish": "gloss"}, "preset": "smoke", "scene": "turntable", "aspect": "16:9"}, "snapshot": base64.b64encode(glb()).decode("ascii")}


def wait_until(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for queue state.")


class QuietServer(RenderServer):
    def finish_request(self, request, client_address):
        self.RequestHandlerClass.log_message = lambda *args: None
        super().finish_request(request, client_address)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = JobStore(Path(self.temp.name), lambda *args: {}, start_worker=False)
        self.dependencies = {"blender": "test-blender", "ffmpeg": "test-ffmpeg", "gpu": "test-gpu"}
        self.server = QuietServer(0, self.store, lambda: self.dependencies)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.store.close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, method, path, value=None, headers=None, raw=None):
        headers = {"Origin": "http://localhost:8080", **(headers or {})}
        if value is not None:
            raw = json.dumps(value).encode()
            headers.setdefault("Content-Type", "application/json")
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        connection.request(method, path, body=raw, headers=headers)
        response = connection.getresponse()
        body = response.read()
        status, output_headers = response.status, dict(response.getheaders())
        connection.close()
        if body and output_headers.get("Content-Type", "").startswith("application/json"):
            body = json.loads(body)
        return status, output_headers, body

    def create_job(self):
        status, _, body = self.request("POST", "/api/jobs", payload())
        self.assertEqual(status, 201, body)
        return body

    def test_every_scene_has_a_manifest(self):
        import spec as render_spec
        from jobs import SCENES
        self.assertLessEqual({scene["id"] for scene in SCENES}, set(render_spec.scene_ids()))

    def test_scenes_carry_manifests_and_random_spec_is_deterministic(self):
        # self.request(method, path, value=None, headers=None, raw=None) -> (status, headers, body)
        status, _, body = self.request("GET", "/api/scenes")
        self.assertEqual(status, 200)
        courtyard = next(s for s in body["scenes"] if s["id"] == "rainy_courtyard")
        self.assertEqual(courtyard["manifest"]["schema"], "modvision.render-spec/0")
        status, _, first = self.request("GET", "/api/spec/random?scene=rainy_courtyard&seed=9")
        status2, _, second = self.request("GET", "/api/spec/random?scene=rainy_courtyard&seed=9")
        self.assertEqual((status, status2), (200, 200))
        self.assertEqual(first, second)
        self.assertEqual(first["seed"], 9)
        status, _, _ = self.request("GET", "/api/spec/random?scene=nope&seed=1")
        self.assertEqual(status, 400)
        status, _, _ = self.request("GET", "/api/spec/random?scene=turntable&seed=abc")
        self.assertEqual(status, 400)
        status, _, body = self.request("GET", "/api/spec/random?scene=turntable")
        self.assertEqual(status, 200)           # server picks a seed
        self.assertIsInstance(body["seed"], int)

    def test_health_readiness_and_cors(self):
        status, headers, body = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(body["ready"])
        self.assertEqual(headers["Access-Control-Allow-Origin"], "http://localhost:8080")
        self.dependencies["ffmpeg"] = None
        self.assertFalse(self.request("GET", "/api/health")[2]["ready"])
        self.assertEqual(self.request("POST", "/api/jobs", payload())[0], 503)

    def test_duplicate_launch_fails_before_reading_or_recovering_jobs(self):
        item = self.create_job()
        with self.store.changed:
            self.store._update(item["jobId"], status="rendering")
        persisted = self.store.directory(item["jobId"]) / "job.json"
        before = persisted.read_bytes()
        with patch("server.JobStore") as second_store, patch("sys.argv", ["server.py", "--port", str(self.server.server_port)]), patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit) as failure:
                main()
            self.assertEqual(failure.exception.code, 1)
            second_store.assert_not_called()
        self.assertEqual(persisted.read_bytes(), before)
        self.assertEqual(self.store.get(item["jobId"])["status"], "rendering")

    def test_keepalive_requests_do_not_inherit_previous_origin(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            for origin, expected_status in (("http://localhost:8080", 200), (None, 200), ("http://127.0.0.1:8081", 200), ("https://foreign.example", 403)):
                connection.request("GET", "/api/health", headers={"Origin": origin} if origin else {})
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, expected_status)
                if origin and expected_status == 200:
                    self.assertEqual(response.getheader("Access-Control-Allow-Origin"), origin)
                else:
                    self.assertIsNone(response.getheader("Access-Control-Allow-Origin"))
        finally:
            connection.close()

    def test_foreign_origins_are_denied_on_reads_mutations_and_files(self):
        for origin in ("https://modvision3d.com", "http://localhost.evil.test:8080", "null", "http://user@localhost:8080", "http://localhost:8080/", "http://localhost:0", "http://127.0.0.2:8080"):
            for method, path in (("GET", "/api/health"), ("GET", "/api/jobs"), ("GET", "/files/anything/video.mp4"), ("OPTIONS", "/api/jobs"), ("POST", "/api/jobs")):
                status, headers, _ = self.request(method, path, headers={"Origin": origin})
                self.assertEqual(status, 403, (method, origin))
                self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_valid_local_origins_and_preflight(self):
        for origin in ("http://localhost:5173", "http://127.0.0.1:8080", "http://[::1]:8080"):
            status, headers, _ = self.request("OPTIONS", "/api/jobs", headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
            self.assertEqual(status, 204)
            self.assertEqual(headers["Access-Control-Allow-Origin"], origin)

    def test_rejects_rebound_host_and_wrong_port(self):
        for host in (f"evil.test:{self.server.server_port}", "localhost:1", "127.0.0.1"):
            self.assertEqual(self.request("GET", "/api/health", headers={"Host": host})[0], 403)

    def test_json_only_mutations_bounded_body_and_malformed_json(self):
        self.assertEqual(self.request("POST", "/api/jobs", raw=b"{}", headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("POST", "/api/jobs", raw=b"{", headers={"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.request("POST", "/api/jobs", raw=b"", headers={"Content-Type": "application/json", "Content-Length": str(MAX_BODY_BYTES + 1)})[0], 413)
        self.assertEqual(self.request("POST", "/api/jobs", raw=b"{}", headers={"Content-Type": "application/json", "Transfer-Encoding": "chunked"})[0], 400)

    def test_server_generates_id_and_rejects_noncanonical_job(self):
        data = payload()
        data["job"]["jobId"] = "../../untrusted"
        status, _, item = self.request("POST", "/api/jobs", data)
        self.assertEqual(status, 201)
        self.assertRegex(item["jobId"], r"^[0-9a-f]{32}$")
        self.assertEqual(item["job"]["total_frames"], 12)
        self.assertEqual(item["job"]["jobId"], item["jobId"])
        for field, value in (("schema", True), ("preset", "unbounded"), ("resolution", [9999, 9999]), ("resolution", [320.0, 180]), ("frame_end", 99999), ("car", "../car.glb"), ("samples", 2048), ("scene", "../../file"), ("engine", "custom")):
            malformed = payload()
            malformed["job"][field] = value
            self.assertEqual(self.request("POST", "/api/jobs", malformed)[0], 400, field)

    def test_queue_limit_cancel_retry_and_delete(self):
        self.store.max_pending = 1
        item = self.create_job()
        self.assertEqual(item["position"], 1)
        self.assertEqual(self.request("POST", "/api/jobs", payload())[0], 429)
        self.assertEqual(self.request("DELETE", "/api/jobs/" + item["jobId"], {})[0], 409)
        self.assertEqual(self.request("POST", "/api/jobs/" + item["jobId"] + "/cancel", {})[2]["status"], "cancelled")
        status, _, retried = self.request("POST", "/api/jobs/" + item["jobId"] + "/retry", {})
        self.assertEqual(status, 201)
        self.assertNotEqual(retried["jobId"], item["jobId"])
        self.assertEqual((self.store.directory(retried["jobId"]) / "snapshot.glb").read_bytes(), glb())
        self.assertEqual(self.request("DELETE", "/api/jobs/" + item["jobId"], {})[0], 200)
        self.assertEqual(self.request("GET", "/api/jobs/" + item["jobId"])[0], 404)

    def test_whitelisted_files_and_mp4_byte_ranges(self):
        item = self.create_job()
        job_id = item["jobId"]
        folder = self.store.directory(job_id)
        (folder / "video.mp4").write_bytes(b"0123456789")
        self.assertEqual(self.request("GET", f"/files/{job_id}/video.mp4")[0], 404)
        with self.store.changed:
            self.store._update(job_id, status="done")
        status, headers, body = self.request("GET", f"/files/{job_id}/video.mp4", headers={"Range": "bytes=2-5"})
        self.assertEqual((status, body), (206, b"2345"))
        self.assertEqual(headers["Content-Range"], "bytes 2-5/10")
        self.assertEqual(self.request("GET", f"/files/{job_id}/video.mp4", headers={"Range": "bytes=-3"})[2], b"789")
        status, headers, body = self.request("GET", f"/files/{job_id}/video.mp4?download=1")
        self.assertEqual((status, body), (200, b"0123456789"))
        self.assertEqual(headers["Content-Disposition"], f'attachment; filename="modvision-{job_id}-video.mp4"')
        for invalid in ("bytes=12-", "bytes=5-2", "bytes=0-1,3-4", "bytes=-0", "potato"):
            self.assertEqual(self.request("GET", f"/files/{job_id}/video.mp4", headers={"Range": invalid})[0], 416)
        for path in (f"/files/{job_id}/job.json", f"/files/{job_id}/snapshot.glb", f"/files/{job_id}/../job.json", "/files/../video.mp4", f"/files/{job_id}/%2e%2e%2fjob.json"):
            self.assertEqual(self.request("GET", path)[0], 404)

    def test_sse_terminal_event_contains_status(self):
        item = self.create_job()
        self.store.cancel(item["jobId"])
        status, headers, body = self.request("GET", f"/api/jobs/{item['jobId']}/events")
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("text/event-stream"))
        self.assertIn(b"event: progress", body)
        self.assertIn(b'"status": "cancelled"', body)


class ValidationTests(unittest.TestCase):
    def test_stock_and_frozen_viewer_finishes_are_accepted(self):
        for finish in ("stock", "solid", "gloss", "matte", "metallic", "satin", "frozen", "chrome", "pearlescent"):
            data = payload()
            data["job"]["paint"]["finish"] = finish
            self.assertEqual(validate_job(data)[0]["paint"]["finish"], finish)

    def test_glb_corruption_and_external_resources_are_rejected(self):
        for snapshot in (b"bad", b"glTF" + b"\x00" * 40, glb()[:-1], glb({"asset": {"version": "2.0"}, "images": [{"uri": "C:/private/file.png"}]}), glb({"asset": {"version": "2.0"}, "buffers": [{"uri": "https://evil.test/a.bin"}]})):
            data = payload()
            data["snapshot"] = base64.b64encode(snapshot).decode()
            with self.assertRaises(JobError):
                validate_job(data)

    def test_presets_are_canonical_for_both_aspects(self):
        for preset in ("smoke", "draft", "film_preview", "film_final", "standard", "cinematic", "4k"):
            landscape = canonical_settings(preset, "turntable", "16:9")
            portrait = canonical_settings(preset, "night_garage", "9:16")
            self.assertEqual(landscape["resolution"], list(reversed(portrait["resolution"])))
            self.assertEqual(landscape["frame_end"], landscape["fps"] * landscape["duration_s"])

    def test_rain_film_and_internal_proof_boundary(self):
        data = payload()
        data['job'].update(scene='rainy_courtyard', preset='film_preview', aspect='9:16')
        spec, _ = validate_job(data)
        self.assertEqual(spec['resolution'], [720, 1280])
        self.assertEqual((spec['engine'], spec['fps'], spec['total_frames']), ('CYCLES', 24, 240))
        for field, value in [('proof_offsets', [12, 60, 108]), ('save_blend', True), ('asset_path', 'private')]:
            invalid = deepcopy(data)
            invalid['job'][field] = value
            with self.assertRaises(JobError):
                validate_job(invalid)

    def test_final_portrait_and_encoding_options_stay_server_owned(self):
        data = payload()
        data['job'].update(scene='rainy_courtyard', preset='film_final', aspect='9:16')
        spec, _ = validate_job(data)
        self.assertEqual(spec['resolution'], [1080, 1920])
        self.assertEqual((spec['samples'], spec['fps'], spec['total_frames']), (192, 24, 240))
        for key, value in [('resolution', [720, 1280]), ('bitrate', 1), ('ffmpeg_args', ['-f', 'null'])]:
            altered = deepcopy(data)
            altered['job'][key] = value
            with self.assertRaises(JobError):
                validate_job(altered)

    def test_spec_is_validated_and_becomes_server_owned_look(self):
        import spec as render_spec
        data = payload()
        data['job'].update(scene='rainy_courtyard', preset='film_preview')
        data['job']['spec'] = render_spec.sample_spec('rainy_courtyard', 5)
        with patch.dict('os.environ', {'MV_RENDER_CAR_IDS': '*'}):
            job, _ = validate_job(data)
        self.assertEqual(job['look']['scene_seed'], 5)
        self.assertIn(job['look']['falling_rain'], (True, False))
        self.assertEqual(job['grain'], data['job']['spec']['look']['grain'])
        plain, _ = validate_job(payload())
        self.assertNotIn('grain', plain)
        self.assertEqual(job['spec']['provenance']['source'], 'random')

    def test_spec_scene_must_match_job_scene_and_look_cannot_be_sent_directly(self):
        import spec as render_spec
        data = payload()
        data['job'].update(scene='turntable', preset='smoke')
        data['job']['spec'] = render_spec.default_spec('rainy_courtyard')
        with patch.dict('os.environ', {'MV_RENDER_CAR_IDS': '*'}):
            with self.assertRaises(JobError):
                validate_job(data)
            direct = payload()
            direct['job']['look'] = {'exposure': 3}
            with self.assertRaises(JobError):
                validate_job(direct)
            broken = payload()
            broken['job']['spec'] = render_spec.default_spec('turntable')
            broken['job']['spec']['look']['exposure'] = 99
            with self.assertRaises(JobError) as caught:
                validate_job(broken)
            self.assertIn('look.exposure', str(caught.exception))


class QueueTests(unittest.TestCase):
    def test_every_preset_has_an_estimate_without_render_history(self):
        with tempfile.TemporaryDirectory() as directory:
            store = JobStore(Path(directory), lambda *args: {}, start_worker=False)
            try:
                for preset in PRESETS:
                    estimate = store.estimate(preset, 'rainy_courtyard', '9:16')
                    self.assertGreater(estimate['estimatedSeconds'], 0)
                    self.assertFalse(estimate['measured'])
            finally:
                store.close()

    def test_one_worker_cancellation_and_late_success_cannot_overwrite_cancel(self):
        entered = threading.Event()
        release = threading.Event()
        calls = []

        def pipeline(job, folder, progress, cancelled):
            calls.append(job["jobId"])
            progress({"status": "rendering", "progress": 0.5, "frame": 6, "totalFrames": 12})
            entered.set()
            release.wait(3)
            # Deliberately return success after cancellation to exercise the race.
            (folder / "video.mp4").write_bytes(b"video")
            return {"secondsPerFrame": 0.01}

        with tempfile.TemporaryDirectory() as temp:
            store = JobStore(Path(temp), pipeline)
            spec, snapshot = validate_job(payload())
            first = store.submit(spec, snapshot)
            self.assertTrue(entered.wait(2))
            second = store.submit(spec, snapshot)
            self.assertEqual(calls, [first["jobId"]])
            store.cancel(first["jobId"])
            self.assertTrue(store.cancel_events[first["jobId"]].is_set())
            with self.assertRaises(JobError):
                store.delete(first["jobId"])
            store.cancel(second["jobId"])
            release.set()
            wait_until(lambda: store.active_id is None)
            self.assertEqual(store.get(first["jobId"])["status"], "cancelled")
            self.assertEqual(calls, [first["jobId"]])
            store.close()

    def test_restart_recovers_queued_jobs_and_marks_interrupted_failed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = JobStore(root, lambda *args: {}, start_worker=False)
            spec, snapshot = validate_job(payload())
            queued = store.submit(spec, snapshot)
            interrupted = store.submit(spec, snapshot)
            with store.changed:
                store._update(interrupted["jobId"], status="rendering", progress=0.5)
            store.close()
            recovered = JobStore(root, lambda *args: {}, start_worker=False)
            self.assertEqual(list(recovered.pending), [queued["jobId"]])
            failed = recovered.get(interrupted["jobId"])
            self.assertEqual(failed["status"], "failed")
            self.assertIn("stopped", failed["error"])
            self.assertEqual(json.loads((root / interrupted["jobId"] / "job.json").read_text())["status"], "failed")
            recovered.close()

    def test_success_and_pipeline_failure_are_persisted(self):
        def pipeline(job, folder, progress, cancelled):
            if job["scene"] == "night_garage":
                raise RuntimeError("Example render failure")
            (folder / "video.mp4").write_bytes(b"video")
            return {"secondsPerFrame": 1.25}

        with tempfile.TemporaryDirectory() as temp:
            store = JobStore(Path(temp), pipeline)
            spec, snapshot = validate_job(payload())
            first = store.submit(spec, snapshot)
            spec["scene"] = "night_garage"
            second = store.submit(spec, snapshot)
            wait_until(lambda: store.get(second["jobId"])["status"] == "failed")
            self.assertEqual(store.get(first["jobId"])["status"], "done")
            self.assertEqual(store.get(first["jobId"])["progress"], 1)
            self.assertIn("video", store.get(first["jobId"])["output"])
            self.assertEqual(store.get(second["jobId"])["error"], "Example render failure")
            self.assertTrue(store.estimate("smoke", "turntable", "16:9")["measured"])
            store.close()


if __name__ == "__main__":
    unittest.main()


def scene_plan(**over):
    """A minimal valid ScenePlan, matching the studio's schema."""
    plan = {
        "camera": {"style": "smooth", "lensMm": 50, "heightM": 1.4, "motionStrength": 0.0},
        "lighting": {"style": "soft_studio", "exposure": 0.0, "rim": True, "practicals": False},
        "effects": {"rain": 0.0, "wetGround": 0.0, "motionBlur": 0.0, "depthOfField": 0.0},
        "shots": [{"id": "a", "start": 0, "end": 10, "action": "slow_orbit", "distanceMultiplier": 1.0}],
        "output": {"fps": 30, "durationS": 10, "resolution": "1080p", "quality": "high"},
    }
    plan.update(over)
    return plan


class ScenePlanTests(unittest.TestCase):
    """The studio's plan owns the output settings; the preset owns the quality ladder."""

    def test_output_settings_follow_the_plan(self):
        settings = canonical_settings("film_final", "turntable", "16:9", scene_plan())
        self.assertEqual(settings["resolution"], [1920, 1080])
        self.assertEqual(settings["fps"], 30)
        self.assertEqual(settings["duration_s"], 10)
        self.assertEqual(settings["total_frames"], 300)

    def test_the_preset_still_owns_samples_and_engine(self):
        settings = canonical_settings("draft", "turntable", "16:9", scene_plan())
        self.assertEqual(settings["samples"], 32)
        self.assertEqual(settings["engine"], "EEVEE")
        self.assertTrue(settings["watermark"])

    def test_vertical_reverses_the_plan_resolution(self):
        settings = canonical_settings("film_final", "turntable", "9:16", scene_plan())
        self.assertEqual(settings["resolution"], [1080, 1920])

    def test_without_a_plan_the_preset_still_decides(self):
        settings = canonical_settings("film_final", "turntable", "16:9")
        self.assertEqual(settings["duration_s"], 10)
        self.assertEqual(settings["fps"], 24)

    def test_a_frame_count_past_the_quality_cap_is_refused(self):
        plan = scene_plan(
            shots=[{"id": "a", "start": 0, "end": 30, "action": "slow_orbit", "distanceMultiplier": 1.0}],
            output={"fps": 60, "durationS": 30, "resolution": "4k", "quality": "ultra"},
        )
        with self.assertRaises(JobError) as caught:
            canonical_settings("smoke", "turntable", "16:9", plan)
        self.assertIn("limit", str(caught.exception))

    def test_a_gap_between_shots_is_refused(self):
        plan = scene_plan(shots=[
            {"id": "a", "start": 0, "end": 4, "action": "slow_orbit", "distanceMultiplier": 1.0},
            {"id": "b", "start": 6, "end": 10, "action": "hero_push_in", "distanceMultiplier": 1.0},
        ])
        with self.assertRaises(JobError) as caught:
            validate_plan(plan)
        self.assertIn("contiguous", str(caught.exception))

    def test_shots_must_cover_the_whole_duration(self):
        plan = scene_plan(shots=[{"id": "a", "start": 0, "end": 4, "action": "slow_orbit", "distanceMultiplier": 1.0}])
        with self.assertRaises(JobError):
            validate_plan(plan)

    def test_an_unknown_shot_action_is_refused(self):
        plan = scene_plan(shots=[{"id": "a", "start": 0, "end": 10, "action": "barrel_roll", "distanceMultiplier": 1.0}])
        with self.assertRaises(JobError):
            validate_plan(plan)

    def test_a_lens_outside_the_schema_is_refused(self):
        plan = scene_plan(camera={"style": "smooth", "lensMm": 400, "heightM": 1.4, "motionStrength": 0.0})
        with self.assertRaises(JobError) as caught:
            validate_plan(plan)
        self.assertIn("lensMm", str(caught.exception))

    def test_an_exposure_outside_the_schema_is_refused(self):
        plan = scene_plan(lighting={"style": "soft_studio", "exposure": 40.0, "rim": True, "practicals": False})
        with self.assertRaises(JobError) as caught:
            validate_plan(plan)
        self.assertIn("lighting.exposure", str(caught.exception))

    def test_a_plan_without_lighting_is_refused(self):
        plan = scene_plan()
        del plan["lighting"]
        with self.assertRaises(JobError):
            validate_plan(plan)

    def test_a_booby_trapped_effect_value_is_refused(self):
        plan = scene_plan(effects={"rain": float("nan"), "wetGround": 0.0, "motionBlur": 0.0, "depthOfField": 0.0})
        with self.assertRaises(JobError):
            validate_plan(plan)

    def test_a_plan_rides_through_validate_job(self):
        data = payload()
        data["job"]["plan"] = scene_plan()
        data["job"]["preset"] = "film_final"
        for key in ("duration_s", "fps", "resolution", "samples", "engine", "frame_start", "frame_end", "total_frames"):
            data["job"].pop(key, None)
        canonical, _ = validate_job(data)
        self.assertEqual(canonical["total_frames"], 300)
        self.assertEqual(canonical["plan"]["camera"]["lensMm"], 50)
