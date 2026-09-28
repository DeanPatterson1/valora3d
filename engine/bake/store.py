"""Verified, portable bake directories, atomically published with LRU eviction and pins."""
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import threading
import time
import uuid
from contextlib import contextmanager

from engine.bake import lock
from engine.bake.key import sha256_file
from engine.bake.lock import ROOT

DEFAULT_ROOT = ROOT / "var" / "bake"
DEFAULT_CAP_GB = 60
MANIFEST = "bake.json"
PINS = "pins.json"
_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
_TEMP = re.compile(r"\.tmp-(.+)-(\d+)-[0-9a-f]+")
_RESERVED = {"schema", "key", "files", "createdNs", "lastRead"}
_last_tick = 0
_tick_lock = threading.Lock()


class CacheCorrupt(RuntimeError):
    """A committed cache cannot be trusted or read."""


def _tick():
    # Windows clocks may repeat: preserve ordering even inside one clock quantum.
    global _last_tick
    with _tick_lock:
        _last_tick = max(time.time_ns(), _last_tick + 1)
        return _last_tick


def _valid_key(key):
    return isinstance(key, str) and _KEY.fullmatch(key) is not None and ".." not in key


def _rmtree(path):
    def retry(function, name, exc):
        os.chmod(name, stat.S_IREAD | stat.S_IWRITE)
        function(name)
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=retry)
    else:                          # Blender 5.0.1 bundles Python 3.11: no onexc yet
        shutil.rmtree(path, onerror=retry)


def _atomic_json(path, value):
    data = json.dumps(value, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    temp = path.with_name(f".{path.name}-{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("x", encoding="utf-8") as target:
            target.write(data)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


class _Writer:
    def __init__(self, directory):
        self.dir = directory
        self._report = {}

    def report(self, value):
        if not isinstance(value, dict):
            raise TypeError("bake report must be a dict")
        if _RESERVED.intersection(value):
            raise ValueError("bake report cannot override manifest fields")
        # Snapshot and validate now, so caller mutations cannot invalidate a commit.
        self._report.update(json.loads(json.dumps(value, allow_nan=False)))


class BakeStore:
    def __init__(self, root=None, cap_bytes=None):
        self.root = Path(root if root is not None else os.environ.get("VALORA_BAKE_ROOT", DEFAULT_ROOT))
        self.cap_bytes = (cap_bytes if cap_bytes is not None else
                          float(os.environ.get("VALORA_BAKE_CACHE_GB", DEFAULT_CAP_GB)) * (1 << 30))
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key):
        if not _valid_key(key):
            raise ValueError(f"invalid bake key: {key!r}")
        return self.root / key

    @contextmanager
    def writer(self, key):
        """Publish only complete bakes; an already verified winner remains authoritative."""
        destination = self.path(key)
        directory = self.root / f".tmp-{key}-{os.getpid()}-{uuid.uuid4().hex}"
        directory.mkdir()
        writer = _Writer(directory)
        try:
            yield writer
            files = {}
            for path in sorted(directory.rglob("*")):
                if path.is_file() and path.name != MANIFEST:
                    files[path.relative_to(directory).as_posix()] = {
                        "sha256": sha256_file(path), "bytes": path.stat().st_size,
                    }
            manifest = {"schema": "valora.bake/1", "key": key, "files": files,
                        "createdNs": time.time_ns(), "lastRead": _tick(), **writer._report}
            _atomic_json(directory / MANIFEST, manifest)
            while True:
                try:
                    os.replace(directory, destination)
                    break
                except OSError:
                    if not destination.is_dir():
                        raise
                    try:
                        existing = self._load(key, "size")
                    except CacheCorrupt:
                        existing = None
                    if existing is not None:
                        break
                    _rmtree(destination)
        finally:
            if directory.exists():
                _rmtree(directory)
        self.prune(protect=(key,))     # never evict the bake just written (its compile reads it next)

    def _load(self, key, verify):
        directory = self.path(key)
        try:
            manifest = json.loads((directory / MANIFEST).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as exc:
            raise CacheCorrupt(f"{key}/{MANIFEST}: {exc}") from exc
        if (not isinstance(manifest, dict) or manifest.get("schema") != "valora.bake/1"
                or manifest.get("key") != key or not isinstance(manifest.get("files"), dict)
                or type(manifest.get("createdNs")) is not int
                or type(manifest.get("lastRead")) is not int):
            raise CacheCorrupt(f"{key}/{MANIFEST}: invalid manifest")
        for relative, info in manifest["files"].items():
            rel = PurePosixPath(relative)
            if (not relative or rel.is_absolute() or ".." in rel.parts
                    or "\\" in relative or ":" in relative or rel.as_posix() != relative
                    or not isinstance(info, dict) or type(info.get("bytes")) is not int
                    or info["bytes"] < 0 or not isinstance(info.get("sha256"), str)
                    or re.fullmatch(r"[0-9a-f]{64}", info["sha256"]) is None):
                raise CacheCorrupt(f"{key}/{MANIFEST}: invalid file {relative!r}")
            if verify == "none":
                continue
            path = directory / relative
            try:
                if not path.is_file() or path.stat().st_size != info["bytes"]:
                    raise CacheCorrupt(f"{key}/{relative}: missing file or size mismatch")
                if verify == "full" and sha256_file(path) != info["sha256"]:
                    raise CacheCorrupt(f"{key}/{relative}: sha256 mismatch")
            except OSError as exc:
                raise CacheCorrupt(f"{key}/{relative}: {exc}") from exc
        return manifest

    def read(self, key, verify="full"):
        """Touch LRU only after verification; size-only reads avoid hashing preview caches."""
        self.path(key)
        if verify not in ("full", "size", "none"):
            raise ValueError(f"unknown cache verification mode: {verify!r}")
        manifest = self._load(key, verify)
        if manifest is not None:
            manifest["lastRead"] = _tick()
            _atomic_json(self.path(key) / MANIFEST, manifest)
        return manifest

    def pins(self):
        try:
            return json.loads((self.root / PINS).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}

    def pin(self, key, reason):
        if not (self.path(key) / MANIFEST).is_file():
            raise KeyError(key)
        pins = self.pins()
        pins[key] = {"reason": reason, "pinnedNs": time.time_ns()}
        _atomic_json(self.root / PINS, pins)

    def unpin(self, key):
        self.path(key)
        pins = self.pins()
        pins.pop(key, None)
        _atomic_json(self.root / PINS, pins)

    def keys(self):
        return sorted(path.name for path in self.root.iterdir()
                      if _valid_key(path.name) and path.is_dir() and (path / MANIFEST).is_file())

    def size(self, key):
        return sum(path.stat().st_size for path in self.path(key).rglob("*") if path.is_file())

    def total_bytes(self):
        return sum(self.size(key) for key in self.keys())

    def prune(self, protect=()):
        """Evict oldest reads first, preserving pins, the `protect` keys and temporary bakes owned by live
        processes. The cap can stay exceeded when only pinned / protected keys remain."""
        for path in self.root.iterdir():
            match = _TEMP.fullmatch(path.name)
            if match and path.is_dir():
                pid = int(match[2])
                if pid != os.getpid() and not lock._pid_alive(pid):
                    _rmtree(path)
        pins = self.pins()
        sizes = {key: self.size(key) for key in self.keys()}
        candidates = []
        for key in sizes:
            if key in pins or key in protect:
                continue
            try:
                manifest = json.loads((self.path(key) / MANIFEST).read_text(encoding="utf-8"))
                tick = manifest.get("lastRead", 0)
                if type(tick) is not int:
                    tick = 0
            except (OSError, ValueError, AttributeError):
                tick = 0
            candidates.append((tick, key))
        total, removed = sum(sizes.values()), []
        for _, key in sorted(candidates):
            if total <= self.cap_bytes:
                break
            self.delete(key)
            total -= sizes[key]
            removed.append(key)
        return removed

    def delete(self, key):
        path = self.path(key)
        if path.exists():
            _rmtree(path)
