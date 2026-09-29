# syntax=docker/dockerfile:1.7
# Valora3D render worker for RunPod Serverless: Blender 5.0.1 (engine/blender_pin.py) + engine/ + ffmpeg + handler.
#
# Build from the repo root (context = repo root; the pinned asset library is a named build context):
#   docker buildx build --platform linux/amd64 -f worker/Dockerfile \
#     --build-context library=../Rendering/assets-in/library \
#     --build-arg ENGINE_SHA=$(git rev-parse HEAD) \
#     -t ghcr.io/<owner>/valora-worker:<engine-sha> --push .
# Network-volume variant: --build-context library=worker/no-library and set VALORA_ASSET_LIBRARY (README "Assets").

ARG CUDA_BASE=nvidia/cuda:12.8.1-base-ubuntu24.04

# ---------------------------------------------------------------- Blender, checksum-verified
FROM ${CUDA_BASE} AS blender
ARG BLENDER_VERSION=5.0.1
# From https://download.blender.org/release/Blender5.0/blender-5.0.1.sha256 (fetched 2026-09-28)
ARG BLENDER_SHA256=8019580ee1b7262e505f4196a00237ccf743c88d205b38d34201510676e60b09
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl xz-utils \
 && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL --retry 3 -o /tmp/blender.tar.xz \
      "https://download.blender.org/release/Blender${BLENDER_VERSION%.*}/blender-${BLENDER_VERSION}-linux-x64.tar.xz" \
 && echo "${BLENDER_SHA256}  /tmp/blender.tar.xz" | sha256sum -c - \
 && mkdir -p /opt/blender \
 && tar -xJf /tmp/blender.tar.xz -C /opt/blender --strip-components=1 \
 && rm /tmp/blender.tar.xz

# ---------------------------------------------------------------- watermark font (Inter, SIL OFL 1.1), checksum-verified
FROM ${CUDA_BASE} AS font
ARG INTER_VERSION=4.1
# sha256 of Inter-4.1.zip and of the TTF inside it, both measured 2026-09-28 from the GitHub release asset
ARG INTER_ZIP_SHA256=9883fdd4a49d4fb66bd8177ba6625ef9a64aa45899767dde3d36aa425756b11e
ARG INTER_TTF_SHA256=78a843fade9d4612a5567302fb595b56976eb5fcebf4fea5a5912d638bafcde3
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl unzip \
 && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL --retry 3 -o /tmp/inter.zip \
      "https://github.com/rsms/inter/releases/download/v${INTER_VERSION}/Inter-${INTER_VERSION}.zip" \
 && echo "${INTER_ZIP_SHA256}  /tmp/inter.zip" | sha256sum -c - \
 && mkdir -p /out \
 && unzip -j /tmp/inter.zip extras/ttf/Inter-SemiBold.ttf LICENSE.txt -d /out \
 && echo "${INTER_TTF_SHA256}  /out/Inter-SemiBold.ttf" | sha256sum -c - \
 && mv /out/LICENSE.txt /out/Inter-OFL.txt \
 && rm /tmp/inter.zip

# ---------------------------------------------------------------- runtime
FROM ${CUDA_BASE}
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8
# python3 + venv for the handler/engine host side; ffmpeg (libx264) for the encode; the X11/GL client libraries
# the official Linux Blender links against even in --background; tini reaps Blender if the handler dies.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 python3-venv ca-certificates ffmpeg tini \
      libx11-6 libxi6 libxxf86vm1 libxfixes3 libxrender1 libxext6 libxrandr2 libxkbcommon0 \
      libsm6 libice6 libgl1 libegl1 libglx0 libgomp1 \
 && rm -rf /var/lib/apt/lists/*

COPY --from=blender /opt/blender /opt/blender
# params.watermark draws with this file (encode.py WORKER_WATERMARK_FONT); the OFL text ships beside it.
COPY --from=font /out/ /usr/share/fonts/valora/
# Fail the build (not the first job) if a library is missing or the build drifted from the pin.
RUN /opt/blender/blender --background --factory-startup --version | tee /tmp/bv \
 && grep -q "^Blender 5.0.1" /tmp/bv && rm /tmp/bv

COPY worker/requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
 && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt \
 && rm /tmp/requirements.txt

# Ubuntu 24.04 ships uid 1000 as "ubuntu"; the worker takes that uid (engine/compiler/sandbox.py also uses 1000).
RUN userdel --remove ubuntu 2>/dev/null || true \
 && useradd --uid 1000 --create-home --shell /usr/sbin/nologin valora

WORKDIR /app
# The ~850 MB library changes far less often than the code: its own layer, BEFORE the code, so a code-only
# release re-pulls only the small code layers. fetch_assets.py writes 644 files / 755 dirs, readable by the worker
# user; keep it out of the chmod below, which would otherwise copy the whole library into a new layer every build.
COPY --from=library . /app/assets-in/library/
RUN if find /app/assets-in/library \( -type f ! -perm -004 \) -o \( -type d ! -perm -005 \) | grep -q .; then \
      echo "asset library has files the worker user cannot read" >&2; exit 1; fi
# Code is root-owned and read-only to the worker user; only var/ and the job root are writable.
COPY engine/ /app/engine/
COPY research/ /app/research/
COPY harness/ /app/harness/
COPY docs/superpowers/specs/2026-09-24-director-layer-design.md /app/docs/superpowers/specs/
COPY worker/ /app/worker/
RUN /opt/venv/bin/python -m compileall -q /app/engine /app/worker /app/harness \
 && mkdir -p /app/var/bake /app/var/variety /tmp/valora-jobs \
 && chown -R valora:valora /app/var /tmp/valora-jobs \
 && chmod -R a+rX /app/engine /app/research /app/harness /app/docs /app/worker

ARG ENGINE_SHA=unknown
ENV VALORA_ENGINE_SHA=${ENGINE_SHA} \
    VALORA_BLENDER_VERSION=5.0.1 \
    BLENDER_EXE=/opt/blender/blender \
    VALORA_DEVICE=OPTIX \
    VALORA_ENGINE_DIR=/app \
    VALORA_ASSET_LIBRARY=/app/assets-in/library \
    VALORA_BAKE_ROOT=/app/var/bake \
    VALORA_VARIETY_DIR=/app/var/variety \
    WORKER_JOB_ROOT=/tmp/valora-jobs \
    WORKER_WATERMARK_FONT=/usr/share/fonts/valora/Inter-SemiBold.ttf \
    WORKER_URL_ALLOW_HOSTS=*.r2.cloudflarestorage.com \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics \
    PATH=/opt/venv/bin:${PATH}

USER valora
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/opt/venv/bin/python", "-u", "-m", "worker.handler"]
