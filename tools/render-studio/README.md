# Render Studio — local render pipeline

Turns a scene directed in the web app into an MP4, on this machine, with Blender and
ffmpeg. This is the "Local GPU" target in the studio's Render tab.

Ported from ModVision's render studio. The pipeline internals are documented in
[PIPELINE.md](PIPELINE.md), which still describes the original in places; the
differences that matter here are listed under **What changed in the port** below.

## Run it

```bash
py tools/render-studio/server.py
```

It binds `127.0.0.1:8765`, loopback only, and the web app talks to it directly from
`localhost:3000`. Nothing leaves the machine.

Needs Blender and ffmpeg on `PATH` (or `BLENDER` / `FFMPEG` set). `GET /api/health`
reports what it found, including the GPU:

```bash
curl -s http://127.0.0.1:8765/api/health
```

## Assets

The rainy courtyard needs ~245 MB of Poly Haven HDRIs, textures and plant models. They
are CC0 but out of git:

```bash
py tools/render-studio/prepare_assets.py
```

Or point `RENDER_STUDIO_ASSETS` at a copy you already have. The studio and night-garage
scenes are built procedurally and need none of it.

## How a render happens

1. The browser exports the edited scene as a GLB — the geometry as the viewer holds it,
   with the file's own materials, deleted parts gone, hidden parts kept.
2. It POSTs `{job, snapshot}` to `/api/jobs`. The job carries the `ScenePlan`.
3. Blender imports the GLB, measures the subject, builds the scene, and traces the
   **same camera path the viewer drew** (`scene_plan_camera.py`).
4. ffmpeg encodes the frames to H.264, two-pass at 1080p and above.
5. The app plays `/files/<jobId>/video.mp4`.

## What changed in the port

- **The scene plan drives the camera.** `scene_plan_camera.py` is a port of
  `apps/web/components/viewer/cameraPath.ts`, so the video is the shot the user
  previewed. It replaces both the orbit and the original five-shot operator.
  `test_scene_plan_camera.py` and `cameraParity.test.ts` assert the same numbers; if
  one fails the other is wrong too.
- **The plan owns the output settings.** Resolution, frame rate and duration come from
  `plan.output`. A preset is now only the quality ladder — engine, samples, watermark —
  and caps the frame count (`MAX_FRAMES`), which is what actually costs GPU time.
- **No car fleet gate.** Models are uploaded by the person rendering them, so there is
  no catalogue licence to check.
- **Exposure follows the plan**, in stops, for every scene.
- The rain scene keeps its atmosphere but not its per-shot exposure and lamp ramps:
  those are indexed by the five-shot operator and mean nothing against a plan path.

## Tests

```bash
py -m unittest discover tools/render-studio -p "test_*.py"
```

They do not need Blender.
