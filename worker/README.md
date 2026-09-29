# Valora3D render worker (RunPod Serverless)

The worker turns one render job into a finished clip:

1. Validate the input.
2. Download the user's `.glb` from a presigned R2 GET. The download is capped at 200 MB, and the file must pass the glTF header check.
3. Run `engine.site_job run` as a subprocess (ingest, then direct, then render).
4. Stream progress from the `SITEJOB` lines and from the count of finished beauty frames.
5. Encode an H.264 MP4 and a poster JPG with ffmpeg, burning in the wordmark when `params.watermark` is set. A `frames.zip` is optional.
6. PUT each result to its presigned R2 URL.
7. Return a result dict.

The engine is a black box: the worker never imports `engine`, and the CLI in `engine/site_job.py` is the whole contract.

| File | Role |
|---|---|
| `handler.py` | RunPod entry (`python -m worker.handler`), job orchestration, progress, cold-start checks |
| `contract.py` | Input validation, error codes |
| `transfer.py` | Presigned download and upload, URL allowlist, GLB header check |
| `sitejob.py` | The `site_job` argv, `SITEJOB` parsing, frame watcher, timeout and tree kill, scrubbed child env |
| `encode.py` | ffmpeg MP4 and poster command lines, `frames.zip` |
| `fake_site_job.py` | A stub `site_job` (same CLI and lines, synthetic frames, no Blender) for tests |
| `local_test.py` | End-to-end run on this machine against a loopback "R2" server |
| `Dockerfile` | Linux image: CUDA base, Blender 5.0.1 (checksum-verified), Inter watermark font (checksum-verified), ffmpeg, engine, handler, non-root user |

## 1. Job contract (the site builds against this)

### Request

The site's API route calls `POST https://api.runpod.ai/v2/<endpoint_id>/run`:

```json
{
  "input": {
    "job_id": "8f3c2a1e-...",
    "glb_url": "https://<acct>.r2.cloudflarestorage.com/uploads/<user>/<sha256>.glb?X-Amz-...",
    "output_put_urls": {
      "video": "https://<acct>.r2.cloudflarestorage.com/results/<job>/video.mp4?X-Amz-...",
      "poster": "https://<acct>.r2.cloudflarestorage.com/results/<job>/poster.jpg?X-Amz-...",
      "frames_zip": "https://.../results/<job>/frames.zip?X-Amz-..."
    },
    "params": {
      "prompt": "slow orbit in the rain at dusk",
      "world": "rain_courtyard",
      "aspect": "9:16",
      "tier": "preview",
      "seed": 12345,
      "duration": 10,
      "paint": "#1a2b3c",
      "finish": "metallic",
      "markers": [],
      "watermark": false
    }
  },
  "webhook": "https://valora3d.com/api/runpod/webhook?job=8f3c2a1e-...&t=<per-job random token>",
  "policy": { "executionTimeout": 5400000, "ttl": 86400000 }
}
```

**Top-level fields**

| Field | Rule |
|---|---|
| `job_id` | The site's own id. Required, `[A-Za-z0-9_-]{1,64}`. It is echoed back and never used as a path. |
| `glb_url` | Required. Must be https. The host must match `WORKER_URL_ALLOW_HOSTS` (default `*.r2.cloudflarestorage.com`). Redirects are refused. |
| `output_put_urls.video` | Required. Sign the PUT with `Content-Type: video/mp4`. |
| `output_put_urls.poster` | Required. Sign the PUT with `Content-Type: image/jpeg`. |
| `output_put_urls.frames_zip` | Optional. Sign the PUT with `Content-Type: application/zip`. The zip holds `frame_000001.png...`, stored uncompressed. |

The presigned PUT URLs must outlive the job. Use at least the tier timeout plus a margin (for example 2 h for a preview, 6 h for a final). A GET that expires before the worker starts returns `GLB_DOWNLOAD_FAILED`, so sign the GET for the queue wait plus a margin.

**`params`**

Every field is optional. An unknown key is `INVALID_INPUT`.

| Field | Rule |
|---|---|
| `prompt` | Up to 2000 characters. An empty prompt still makes a clip. |
| `world` | A world id from `py -m engine.site_job worlds`. The engine rejects an id it does not offer, and the worker returns `INPUT_REJECTED`. |
| `aspect` | `9:16` or `16:9`. When omitted, the director chooses (default 9:16). |
| `tier` | `preview` (540 px short side, 16 spp) or `final` (1080 px, adaptive up to 1024/2048 spp). The default is `preview`. |
| `seed` | An integer from 0 to 2^31−1. |
| `duration` | Seconds, from 3 to 30 (the engine's `DURATION_RANGE`). The site offers 8 to 12. When omitted, the director rolls it. |
| `paint` | `#rrggbb`. It is sent together with `finish`. |
| `finish` | `gloss` (the default), `metallic`, `satin` or `matte`. It is used only when `paint` is set. |
| `watermark` | `true` or `false` (the default). When `true`, a subtle "valora3d.com" wordmark is burned into the bottom-right of the MP4 **and** the poster: white at 60 % opacity with a faint shadow, sized from the frame's short side (about 23 px at 540 px, 45 px at 1080 px) with a matching margin, so 9:16 and 16:9 look the same. The font is Inter SemiBold (SIL OFL 1.1), baked into the image. If the font file is missing (a local run outside the image), the clip is still made unmarked, `watermarked` is `false` and `warnings` says why. Any other type is `INVALID_INPUT`. The site must read `watermarked`, not assume it. |
| `markers` | At most 8 items, each `{anchor: {...}, text: string of at most 280 characters, ...}`. **Today's `site_job run` has no `--markers` option.** The worker detects that from `run --help`, renders anyway, and adds a warning. Markers start working without a worker change once the engine adds the flag. |

### Progress (while `IN_PROGRESS`)

The worker sends progress with `runpod.serverless.progress_update`. The site reads it from `GET /v2/<endpoint>/status/<runpod_id>`, whose `output` field holds the latest payload while the job runs. This is per the RunPod docs; confirm it on the first deploy:

```json
{"job_id": "8f3c...", "stage": "render", "status": "RENDERING", "frame": 42, "total_frames": 240}
```

A stage change is sent every time. Frame ticks are sent at most every `WORKER_PROGRESS_MIN_S` seconds (default 5).

| Worker `stage` | Site `RenderJob.status` |
|---|---|
| RunPod `IN_QUEUE` | `QUEUED` |
| `downloading`, `ingest`, `direct` | `PREPARING` |
| `render` (`frame` / `total_frames` are live) | `RENDERING` |
| `encoding` | `ENCODING` |
| `uploading` | `UPLOADING` |
| `done` | `COMPLETE` |

### Result: success

RunPod `status: COMPLETED`. `output` holds:

```json
{
  "status": "succeeded",
  "job_id": "8f3c...",
  "outputs": {
    "video":  {"bytes": 4812345, "content_type": "video/mp4"},
    "poster": {"bytes": 81234,   "content_type": "image/jpeg"},
    "frames_zip": {"bytes": 312345678, "content_type": "application/zip"}
  },
  "video": {"width": 540, "height": 960, "fps": 24.0, "frames": 240, "duration_s": 10.0},
  "requested_duration_s": 10.0,
  "watermarked": false,
  "frames": 240,
  "fps": 24.0,
  "tier": "preview",
  "render_seconds": 512.3,
  "gpu_seconds": 571.9,
  "glb_bytes": 5422412,
  "timings": {"download_s": 0.8, "site_job_s": 571.9, "ingest_s": 9.1, "direct_s": 14.2, "render_s": 512.3,
              "engine_total_s": 540.6, "encode_s": 6.2, "upload_s": 1.4, "total_s": 580.7},
  "direct": {"source": "llm", "direction": "...", "world": "rain_courtyard",
             "format": {"aspect": "9:16", "durationS": 10, "fps": 24}, "unsupported": [], "rerolls": 0,
             "providerError": null},
  "pin": {"worker": "1", "blender": "5.0.1", "engineSha": "<git sha>", "assetsHash": "<sha256 of manifest>",
          "assetsMissing": 0, "gpu": "NVIDIA GeForce RTX 4090"},
  "warnings": []
}
```

- `video.duration_s` is the clip's real length (`frames / fps`). `requested_duration_s` echoes `params.duration`, or `null` when the director chose the length.
- `watermarked` is `true` only when the wordmark was actually burned into both the MP4 and the poster.

The objects are already at the R2 keys the site signed. The site serves them with short-lived presigned GETs.

`render_seconds` is the engine's own Blender render time. `gpu_seconds` is the wall time of the whole `site_job` process. The whole billed job is longer than both, so see §5 for cost.

### Result: failure

RunPod `status: FAILED`. `error` is `"<CODE>: <user-safe message>"`, and `output` still holds:

```json
{
  "status": "failed", "job_id": "8f3c...",
  "error_code": "INPUT_REJECTED", "error_message": "The model or request was rejected by the renderer.",
  "error_detail": "input rejected: the director could not make a night_street clip for this model at 16:9; ...",
  "retryable": false, "stage": "direct", "timings": {"download_s": 0.4, "site_job_s": 20.1, "total_s": 20.6},
  "pin": {...}, "warnings": [], "log_tail": ["...last 20 non-SITEJOB lines..."]
}
```

- Show `error_message` to users.
- Store `error_detail` and `log_tail` for operators only.
- Refund the credits on every failure. Auto-retry once when `retryable` is true.

| Code | Retryable | Meaning |
|---|---|---|
| `INVALID_INPUT` | no | The request does not match the contract: a bad field, or a URL scheme or host that is not allowed. |
| `GLB_DOWNLOAD_FAILED` | yes | The GET failed (expired signature, network, or a redirect). |
| `GLB_TOO_LARGE` | no | The file is over `WORKER_MAX_GLB_BYTES` (200 MB). |
| `GLB_INVALID` | no | The file is not binary glTF 2 (magic, version, length or JSON chunk). |
| `INPUT_REJECTED` | no | The engine refused the input: `site_job` exit 5 (world or paint), or an ingest rejection (external URIs, over 5M vertices, an image over 64 MB, malformed). |
| `RENDER_FAILED` | yes | `site_job` exit 1 after ingest, a Blender crash, or no `done` line. |
| `RENDER_TIMEOUT` | yes | The job ran past the tier timeout. The whole process tree is killed. |
| `FRAMES_MISSING` | yes | The frames are not contiguous, or the count does not match `site_job.json`. |
| `ENCODE_FAILED` | yes | ffmpeg failed. |
| `UPLOAD_FAILED` | yes | A PUT failed after 3 attempts. A 4xx other than 408 or 429 is not retried. |
| `WORKER_MISCONFIGURED` | yes | Blender or ffmpeg is missing, or the asset library is incomplete (see §3). Alert on this code. |
| `INTERNAL` | yes | Anything unexpected. |

RunPod's own terminal states are `CANCELLED` (after `POST /cancel/<id>`) and `TIMED_OUT` (the `executionTimeout` was hit). They carry no worker `output`. Treat both as failures and refund.

### Webhook (the site's receiving route)

RunPod POSTs the same JSON as `GET /status/<id>` to the request's `webhook` URL once the job is terminal: `{"id", "status": "COMPLETED"|"FAILED"|"CANCELLED"|"TIMED_OUT", "output", "error"?, "delayTime", "executionTime"}`. RunPod does not sign webhooks, so the route must not trust the body:

1. Put an unguessable per-job token in the webhook URL (`?t=`). Store its hash on the job row, and reject a mismatch.
2. Confirm by calling `GET /v2/<endpoint>/status/<id>` with the RunPod API key, which lives in a Worker secret. Act only on that response.
3. Make the handler idempotent on the RunPod job id, because a webhook may arrive twice. Only the first terminal transition debits or refunds.
4. Keep a poll fallback: a cron re-checks jobs still `IN_PROGRESS` well past their ETA, in case a webhook is lost.

### Timeouts (set them, or long renders die)

The worker's own limit is `WORKER_TIMEOUT_PREVIEW_S` (default 3600) or `WORKER_TIMEOUT_FINAL_S` (default 14400). It passes Blender `--timeout` = that limit − 300.

RunPod's **execution timeout defaults to 10 minutes**. Raise it on the endpoint, or per request with `policy.executionTimeout` in ms, above the worker limit: 90 min for a preview, 4.5 h for a final. Final renders at 1024 spp are unmeasured (§5).

## 2. Build and push the image

**Normal path: GitHub Actions** (`.github/workflows/worker-image.yml`). Every push to `worker/runpod` that touches
`worker/`, `engine/`, `research/` or `harness/` builds the image and pushes `ghcr.io/<owner>/valora-worker:<12-char sha>`.
No workstation Docker is needed. The pinned library comes from Poly Haven, not from a workstation:
`worker/assets-lock.json` maps each manifest path to its Poly Haven URL (matched by content, because some files were
renamed locally), and `worker/tools/fetch_assets.py` downloads them and fails on any sha256 that differs from
`engine/assets/manifest.json`. After changing the manifest, regenerate the lock on a machine that has the library:
`py worker/tools/lock_assets.py`. The fetcher refuses a stale lock.

Manual path, for a machine with Docker:

No Docker was available where this was written. The Dockerfile has not been built yet, so the first build is its test. The build itself checks the Blender checksum and fails if `blender --version` is not 5.0.1.

```bash
# From the repo root (a Rendering checkout at the engine commit you want to ship).
# The pinned asset library is gitignored; it lives in the main checkout's assets-in/library.
echo $GHCR_TOKEN | docker login ghcr.io -u <github-user> --password-stdin
docker buildx build --platform linux/amd64 -f worker/Dockerfile \
  --build-context library=../Rendering/assets-in/library \
  --build-arg ENGINE_SHA=$(git rev-parse HEAD) \
  -t ghcr.io/<owner>/valora-worker:$(git rev-parse --short HEAD) --push .
```

- **Tag by engine sha, and never deploy `latest`.** The endpoint pins one image, so every clip is traceable through `pin.engineSha` and `pin.assetsHash`.
- A private GHCR image needs a RunPod "container registry auth" entry, made from a GitHub PAT with `read:packages`.
- **Image size (eng, unmeasured):**

  | Part | Size |
  |---|---|
  | CUDA base | ~0.2 GB |
  | Blender 5.0.1 unpacked | ~1.2 GB |
  | ffmpeg and libraries | ~0.3 GB |
  | Python venv | ~0.1 GB |
  | Asset library | 0.9 GB (208 files, 888 MB measured 2026-09-28) |
  | **Total** | **~2.7 GB** |

**In-container checks, once you have a GPU box with Docker:**

```bash
docker run --rm --gpus all ghcr.io/<owner>/valora-worker:<sha> /opt/blender/blender -b --factory-startup --version
docker run --rm --gpus all --entrypoint /opt/venv/bin/python ghcr.io/<owner>/valora-worker:<sha> \
  -m worker.handler --test_input '{"input": {...}}'     # RunPod SDK local mode
```

Before selling from the cloud, diff a rendered golden against the Windows 5.0.1 goldens the owner graded. A different GPU model and OS can drift the look (audit §4.3). A regrade is an owner step.

## 3. Assets (the 888 MB pinned library)

`engine/assets/manifest.json` pins 208 files by sha256. It covers Poly Haven textures, HDRIs and plants, and totals 888 MB, measured in the main checkout on 2026-09-28. The files themselves (`assets-in/library/`) are gitignored.

A missing file does not fail the engine: its block silently builds a **procedural fallback**, which looks different from what the owner graded. So at cold start the worker checks that every manifest path exists. By default it refuses every job with `WORKER_MISCONFIGURED` if any file is missing (`WORKER_REQUIRE_ASSETS=1`). The engine itself re-checks each sha256 when it uses a file.

| Option | How | Trade-off |
|---|---|---|
| **Bake into the image (default)** | `--build-context library=../Rendering/assets-in/library` | Simplest, with no credentials or extra cold-start download. The image is ~0.9 GB bigger. Assets change with the image tag, so `pin.assetsHash` is exact. |
| Network volume | Build with `--build-context library=worker/no-library`. Create a RunPod network volume and copy `assets-in/library` onto it once. Attach it to the endpoint and set `VALORA_ASSET_LIBRARY=/runpod-volume/valora/library`. | A smaller image. But it pins the endpoint to the volume's datacenter, which shrinks the GPU pool, and the volume can drift from the manifest (the startup check catches missing files, and the engine catches bad hashes). |
| Fetch from R2 at cold start | Not implemented. | It would need R2 read credentials in the container env, and 900 MB per cold start. With `refresh_worker` that is every job. Rejected. |

## 4. Create the RunPod endpoint (owner: account + spend cap first)

Console path: Serverless → New Endpoint → Custom (Docker image).

| Setting | Recommendation |
|---|---|
| Image | `ghcr.io/<owner>/valora-worker:<engine-sha>` |
| GPU | **24 GB or more.** RTX 4090 (24 GB) is the price/performance pick for Cycles. L40S or RTX 6000 Ada (48 GB) are fallbacks for heavy scenes or volumes (phase 6). Pick one SKU per endpoint so looks do not mix (render-core spec H3). |
| CUDA versions | Allow 12.8 and newer only. The base image declares `cuda>=12.8`, which a host with an older driver refuses at start. |
| Workers | Min (active) 0; max 2 to 3 to start (this also caps spend); GPUs per worker 1. |
| Idle timeout | 5 s. Every job recycles its container (`refresh_worker`, §6), so idle time buys nothing. |
| FlashBoot | On. |
| Execution timeout | 4.5 h. Per-request `policy.executionTimeout` can lower it for previews. |
| Container disk | 30 GB. A 12 s final is 288 × 1080×1920 PNG, about 2–3 GB, plus the zip and Blender temp. |
| Env | See the table below. Secrets use RunPod Secrets: `{{ RUNPOD_SECRET_anthropic_key }}`. |

**Environment variables**

| Name | Default in the image | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | unset | The LLM director. When it is unset, the engine's fallback director still makes a clip (`direct.source` = `fallback`, `providerError` says why). See §6 for the risk. |
| `VALORA_VARIETY_SECRET` | unset | **Required.** At least 32 characters; signs the director's variety-memory tokens (engine/director/memory.py). Without it every job fails at `direct` with `RENDER_FAILED`. Store it as a RunPod Secret: `{{ RUNPOD_SECRET_valora_variety_secret }}`. |
| `VALORA_DIRECTOR_MODEL` | engine default | The director model override. |
| `VALORA_PROVIDER` | `anthropic` | Or `fake:<fixture>` for smoke tests. |
| `VALORA_DEVICE` | `CUDA` | Or `OPTIX`. CUDA is the default: measured on RunPod RTX 4090 2026-09-29 (golden_field preview, 90 frames), OptiX spent 414 s compiling kernels on every fresh container before frame 1, CUDA 16 s, with the same per-frame time (~5.5 s) and SSIM 0.98 between the two clips (render noise). |
| `WORKER_URL_ALLOW_HOSTS` | `*.r2.cloudflarestorage.com` | Comma-separated host globs for every GET and PUT. Add an R2 custom domain here if you sign against one. |
| `WORKER_MAX_GLB_BYTES` | 209715200 | The download cap. |
| `WORKER_TIMEOUT_PREVIEW_S` / `WORKER_TIMEOUT_FINAL_S` | 3600 / 14400 | The whole-`site_job` limit per tier. |
| `WORKER_PROGRESS_MIN_S` | 5 | The frame-tick throttle. |
| `WORKER_REFRESH_AFTER_JOB` | 1 | Recycle the container after every job. |
| `WORKER_REQUIRE_ASSETS` | 1 | Refuse jobs when the asset library is incomplete. |
| `VALORA_ASSET_LIBRARY` | `/app/assets-in/library` | Point it at a network volume (§3). |
| `WORKER_WATERMARK_FONT` | `/usr/share/fonts/valora/Inter-SemiBold.ttf` | The TTF for `params.watermark`. The image downloads Inter 4.1 and checks the zip's and the TTF's sha256. |
| `VALORA_ENGINE_SHA` | build arg | Echoed in `pin.engineSha`. |
| Test only: `WORKER_ALLOW_INSECURE_URLS`, `WORKER_SITE_JOB_CMD`, `WORKER_SKIP_READY_CHECKS`, `WORKER_KEEP_WORKDIR` | unset | Never set these on the endpoint. |

**Cold start (eng, unmeasured).**

- The first pull of the ~2.7 GB image on a host takes about 1–3 minutes.
- On a host that has cached it (FlashBoot), the container starts in about 5–20 s. The handler's warm-up then takes a few seconds: an `nvidia-smi` query and the asset existence check.
- Every job then launches Blender twice (ingest and compile), at about 2–5 s each.

Measure the cold start from RunPod's `delayTime` on the first jobs, and record the population and the date.

## 5. Cost per clip (method; no number is quoted until measured)

RunPod serverless bills each worker per second, from container start to stop. That covers the cold start, the job and the idle timeout. Per job:

```
billed_s  = cold_start_s + executionTime_s + idle_timeout_s    (executionTime/delayTime from GET /status)
cost_usd  = billed_s x (current $/s of the chosen GPU class, from the RunPod pricing page on the day)
```

Estimate `cold_start_s` from `delayTime` minus the queue wait. The worker's `timings.total_s` is about the same as `executionTime`.

**Measurement recipe:**

1. For each graded world and each tier, run N ≥ 5 jobs with the shortest and the longest offered duration (8 and 12 s).
2. Log `timings`, `render_seconds`, `frames`, `pin.gpu`, `delayTime` and `executionTime`.
3. Report the median and p90 of seconds per frame and of `cost_usd`, with the population (world, tier, duration, GPU, engine sha) and the date.
4. Set the credit prices from the p90, not the median.

Starting points from the audit, not quotes:

- Preview targets ≤ 2 s/frame at 540p. A 10 s clip is 240 frames, so about 10 minutes of GPU time plus overhead.
- The final tier is unmeasured at 1024 spp. The older 192 spp film measured about 35 s/frame on an RTX 5080, which is about 2.9 GPU-hours per 10 s clip.

The site should store `gpu_seconds` and `billed_s` per job for the render-core `rc_cost_samples` table.

## 6. Security model (untrusted uploads)

**Why RunPod cannot give per-process network isolation.** The plan's rule is "import uploads in a container with no network". RunPod serverless cannot provide that: the worker container needs the network to receive jobs, report progress and PUT results, and RunPod has no `--network=none` for one process inside it. Blender and `site_job` themselves never need the network. Blender runs with `--offline-mode`, and the engine never downloads (`engine/assets.py`). But a malicious GLB that exploited a Blender importer bug **would** have network access.

**Mitigations in this worker:**

- **`.glb` only.**
  - The worker checks the header (magic, version 2, declared length, JSON chunk).
  - The 200 MB cap is enforced while streaming.
  - Then the engine's ingest limits apply: embedded data only, no external URIs, ≤ 5M vertices, and ≤ 64 MB per image.
  - `.blend`, FBX and OBJ are never accepted.
- **Blender runs locked down:** `--factory-startup --disable-autoexec --offline-mode` (`engine/blender_cli.py`).
- **A disposable container.** `refresh_worker: true` recycles the container after **every** job, so a compromised job cannot persist into, or read, the next user's job. The job directory is a random uuid under `/tmp` and is deleted after the job.
- **No standing secrets.** Per-job presigned URLs are scoped to one GET and one PUT per output, and expire. The worker holds no R2 keys, no Supabase keys and no site secrets.
- **Scrubbed child environment.** The `site_job` and Blender children get an allowlisted env, so RunPod's `RUNPOD_*` job-reporting credentials are withheld.
- **A non-dumpable handler.** The handler calls `prctl(PR_SET_DUMPABLE, 0)`, so a same-uid child cannot read the handler's `/proc/<pid>/environ` or ptrace it.
- **Non-root.** The worker runs as uid 1000, and the code in `/app` is root-owned and read-only to it.
- **URL allowlist, no redirects.** A crafted input cannot aim the worker's GET or PUT at internal services (SSRF), because only `WORKER_URL_ALLOW_HOSTS` is reachable and redirects are refused.
- **Hard timeout.** The whole process group is killed.

**Residual risks (owner decision):**

1. **`ANTHROPIC_API_KEY` is in the container**, because `site_job` runs the director in the same process tree as Blender. A Blender exploit could read and exfiltrate it.
   - Mitigate today: use a dedicated key with a low monthly spend limit, and rotate it.
   - The proper fix is to run ingest and direct on a trusted box and give the worker only the finished script. That needs a `--script` input on `site_job`, owned by the renderer-engine track. It is the render-core spec's `trusted` worker flag.
   - The alternative is to leave the key unset and ship the fallback director only.
2. The exploit would still have outbound network access during that one job (see above).
3. The RunPod reporting key is in the handler's memory. Being non-dumpable blocks the same-uid `/proc` and ptrace routes, but a kernel-level escape is out of scope.

## 7. Local testing (no Docker, no GPU needed for the stub)

```bash
py -m pytest worker/tests                      # 134 tests: contract, transfer, SITEJOB parsing, ffmpeg argv, handler
py -m worker.local_test                        # stub site_job, preview, 3 s, CC0 ToyCar from assets-in/models
py -m worker.local_test --mode reject          # other stub modes: ingest_reject | error | noframes | hang
py -m worker.local_test --zip --keep out/      # also request frames.zip; keep video.mp4 + poster.jpg
py -m worker.local_test --engine --provider fake:<fixture>   # REAL engine + Blender on this GPU (slow)
```

`local_test` starts a loopback HTTP server that plays R2: it serves `GET /model.glb` and stores `PUT /out/<name>`. It then runs the handler exactly as RunPod would and checks the MP4 with ffprobe (h264, yuv420p).

## 8. Asks for the renderer-engine track (the worker adapts automatically, or with a one-line change)

1. Make an ingest `IngestRejected` exit 5 instead of 1. The worker currently infers `INPUT_REJECTED` from an ingest-stage failure whose error does not start with "Blender".
2. Add `site_job run --markers FILE`. The worker already passes it the moment `run --help` lists it.
3. Add `site_job run --script FILE` (a pre-directed script), so the director and its API key can move off the GPU worker (§6).
