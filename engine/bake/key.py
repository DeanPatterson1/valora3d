"""Portable content hashes shared by the host and Blender bake stages."""
import hashlib
import json
import math


def _normalize(value):
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("bake key dictionary keys must be strings")
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("bake key numbers must be finite")
        return int(value) if value.is_integer() else value
    return value


def bake_key(ref, env):
    """Hash canonical inputs; METHODS R9 excludes tier so preview and final share one bake."""
    obj = _normalize({"ref": {k: v for k, v in ref.items() if k != "tier"},
                      "env": {k: v for k, v in env.items() if k != "tier"}})
    data = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(data.encode("ascii")).hexdigest()


def sha256_file(path, chunk=1 << 20):
    """Stream large simulation files without loading them into memory."""
    if chunk < 1:
        raise ValueError("chunk must be positive")
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for data in iter(lambda: source.read(chunk), b""):
            digest.update(data)
    return digest.hexdigest()


def sha256_files(paths):
    """Hash concatenated ASCII SHA256 hex digests in caller order (bake.py, build.py)."""
    digest = hashlib.sha256()
    for path in paths:
        digest.update(sha256_file(path).encode("ascii"))
    return digest.hexdigest()
