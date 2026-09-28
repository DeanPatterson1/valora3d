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
# Code is root-owned and read-only to the worker user; only var/ and the job root are writable.
COPY engine/ /app/engine/
COPY research/ /app/research/
COPY harness/ /app/harness/
COPY docs/superpowers/specs/2026-09-24-director-layer-design.md /app/docs/superpowers/specs/
COPY worker/ /app/worker/
COPY --from=library . /app/assets-in/library/
RUN /opt/venv/bin/python -m compileall -q /app/engine /app/worker /app/harness \
 && mkdir -p /app/var/bake /app/var/variety /tmp/valora-jobs \
 && chown -R valora:valora /app/var /tmp/valora-jobs \
 && chmod -R a+rX /app

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
    WORKER_URL_ALLOW_HOSTS=*.r2.cloudflarestorage.com \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics \
    PATH=/opt/venv/bin:${PATH}

USER valora
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/opt/venv/bin/python", "-u", "-m", "worker.handler"]
