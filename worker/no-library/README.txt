Empty asset library for `docker buildx build --build-context library=worker/no-library`.
Use it only when the pinned asset library comes from a RunPod network volume instead
(set VALORA_ASSET_LIBRARY to the mounted path). See worker/README.md "Assets".
