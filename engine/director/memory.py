"""Variety memory (spec §6 layer 3): per user and per subject, the directions used and the values the
user disliked. Local files only (under var/, gitignored).
Privacy: users are identified only by tokens this server issues (random + HMAC-SHA256 tag keyed by a
server secret: VALORA_VARIETY_SECRET, else a 32-byte key file <root>/.secret created on first use with
owner-only permissions). A fabricated or altered token is rejected. File and directory names are hashes
of the token and subject key, never raw input, so no path can escape the root. Every stored value is
validated (catalog values, id == its axes, source enum, numeric ranges), so no free text can reach a
file, and reads filter anything that does not look like a stored value. Files are bounded, writes are
atomic, a corrupt or oversized file reads as empty, and forget(user) serves deletion.
Concurrency: an OS file lock (released by the OS if the holder dies, so it is never broken while
live) plus an in-process lock per path, around read -> roll -> record. A lock that stays busy past
LOCK_TIMEOUT_S raises MemoryBusy; the caller then runs without memory (it never writes unlocked)."""
import contextlib
import datetime
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

from engine.director.direction import AXES, make_id

MEMORY_ENV, SECRET_ENV = "VALORA_VARIETY_DIR", "VALORA_VARIETY_SECRET"
DEFAULT_DIR = Path(__file__).resolve().parents[2] / "var" / "variety"
SOURCES = ("dice", "more_like_this", "interim", "replay")
MAX_ENTRIES = 50           # (eng)
MAX_DISLIKES_PER_AXIS = 3  # (eng)
MAX_FILE_BYTES = 256_000   # a full file is ~6 KB; anything past this is not ours and reads as empty
LOCK_TIMEOUT_S = 10.0      # (eng)
SECRET_BYTES = 32
_TOKEN = re.compile(r"^u_[A-Za-z0-9_-]{32}\.[0-9a-f]{22}$")
_SUBJECT = re.compile(r"^(?:[0-9a-f]{16}|s_[A-Za-z0-9_-]{16,64})$")
_VALUE = re.compile(r"^[a-z0-9_]{1,40}$")
_THREAD_LOCKS, _THREAD_LOCKS_GUARD = {}, threading.Lock()


class MemoryBusy(RuntimeError):
    pass


def _oslock(fd):
    """Non-blocking exclusive lock on byte 0; raises OSError when another holder has it."""
    if sys.platform == "win32":
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _osunlock(fd):
    if sys.platform == "win32":
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_UN)


def _tag(secret, body):
    return hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()[:22]


def _stored_id(i):
    return isinstance(i, str) and len(parts := i.split("/")) == len(AXES) and all(_VALUE.match(p) for p in parts)


class VarietyMemory:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get(MEMORY_ENV) or DEFAULT_DIR)
        self._secret = None

    def _key_bytes(self):
        if self._secret is not None:
            return self._secret
        env = os.environ.get(SECRET_ENV)
        if env:
            if len(env) < 16:
                raise ValueError(f"{SECRET_ENV} must be at least 16 characters")
            self._secret = env.encode()
            return self._secret
        p = self.root / ".secret"
        self.root.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            # Write the key fully under a temp name, then link it into place: a concurrent reader sees
            # either no file or all 32 bytes, and a losing writer keeps the winner's key.
            fd, tmp = tempfile.mkstemp(dir=self.root, prefix=".secret-", suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(secrets.token_bytes(SECRET_BYTES))
                os.chmod(tmp, 0o600)
                with contextlib.suppress(FileExistsError):
                    os.link(tmp, p)
            finally:
                os.remove(tmp)
        key = p.read_bytes()
        if len(key) != SECRET_BYTES:
            raise ValueError("variety memory: the key file is damaged; delete it to re-issue user tokens")
        self._secret = key
        return key

    def issue_user_token(self):
        body = "u_" + secrets.token_urlsafe(24)               # 32 url-safe characters
        return f"{body}.{_tag(self._key_bytes(), body)}"

    def valid_token(self, token):
        if not isinstance(token, str) or not _TOKEN.match(token):
            return False
        body, tag = token.rsplit(".", 1)
        return hmac.compare_digest(tag, _tag(self._key_bytes(), body))

    def _dir(self, user):
        if not self.valid_token(user):
            raise ValueError("variety memory: not a user token issued by this server")
        return self.root / hashlib.sha256(f"valora-variety:{user}".encode()).hexdigest()[:24]

    def _path(self, user, subject):
        if not isinstance(subject, str) or not _SUBJECT.match(subject):
            raise ValueError("variety memory: bad subject key")
        return self._dir(user) / f"{hashlib.sha256(subject.encode()).hexdigest()[:24]}.json"

    @contextlib.contextmanager
    def locked(self, user, subject):
        p = self._path(user, subject).with_suffix(".lock")
        p.parent.mkdir(parents=True, exist_ok=True)
        with _THREAD_LOCKS_GUARD:
            tlock = _THREAD_LOCKS.setdefault(str(p), threading.Lock())
        timeout = LOCK_TIMEOUT_S
        deadline, wait = time.monotonic() + timeout, 0.01
        if not tlock.acquire(timeout=timeout):
            raise MemoryBusy("variety memory is busy for this user and subject")
        fd = None
        try:
            fd = os.open(p, os.O_CREAT | os.O_RDWR, 0o600)
            while True:
                try:
                    _oslock(fd)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise MemoryBusy("variety memory is busy for this user and subject") from None
                    time.sleep(wait)
                    wait = min(wait * 2, 0.2)
            try:
                yield
            finally:
                _osunlock(fd)
        finally:
            if fd is not None:
                os.close(fd)
            tlock.release()

    def _load(self, user, subject):
        p = self._path(user, subject)
        empty = {"entries": [], "dislikes": {}}
        try:
            if p.stat().st_size > MAX_FILE_BYTES:
                return empty
            doc = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(doc, dict) or not isinstance(doc.get("entries"), list) \
                    or not isinstance(doc.get("dislikes", {}), dict):
                return empty
        except (OSError, ValueError):
            return empty
        entries = [e for e in doc["entries"] if isinstance(e, dict) and _stored_id(e.get("id"))]
        dislikes = {a: [v for v in vals if isinstance(v, str) and _VALUE.match(v)]
                    for a, vals in doc.get("dislikes", {}).items() if a in AXES and isinstance(vals, list)}
        return {"entries": entries[-MAX_ENTRIES:],
                "dislikes": {a: v[-MAX_DISLIKES_PER_AXIS:] for a, v in dislikes.items() if v}}

    def _save(self, user, subject, doc):
        p = self._path(user, subject)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(doc)
        if len(data.encode()) > MAX_FILE_BYTES:              # unreachable with the caps; never write it
            raise ValueError("variety memory: record too large")
        fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data)
            os.replace(tmp, p)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def recent(self, user, subject):
        return [e["id"] for e in self._load(user, subject)["entries"]]

    def record(self, user, subject, direction, *, seed, duration_s, known):
        axes = direction.axes()
        bad = [a for a in AXES if axes[a] not in known.get(a, ()) or not _VALUE.match(str(axes[a]))]
        if bad or direction.id != make_id(axes) or direction.source not in SOURCES:
            raise ValueError("variety memory: refusing a record that is not a validated catalog direction")
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2 ** 31:
            raise ValueError("variety memory: bad seed")
        if isinstance(duration_s, bool) or not isinstance(duration_s, (int, float)) or not 1 <= duration_s <= 60:
            raise ValueError("variety memory: bad duration")
        doc = self._load(user, subject)
        doc["entries"] = (doc["entries"] + [{"id": direction.id, "seed": seed, "durationS": duration_s,
                                             "source": direction.source,
                                             "day": datetime.date.today().isoformat()}])[-MAX_ENTRIES:]
        self._save(user, subject, doc)

    def avoided(self, user, subject):
        return {a: list(v) for a, v in self._load(user, subject)["dislikes"].items()}

    def dislike(self, user, subject, avoid, *, known):
        if not isinstance(avoid, dict):
            raise ValueError("variety memory: dislikes must be {axis: [values]}")
        bad = [f"{a}={v}" for a, vals in avoid.items() for v in (vals if isinstance(vals, (list, tuple)) else [vals])
               if a not in AXES or not isinstance(vals, (list, tuple)) or v not in known.get(a, ())
               or not _VALUE.match(str(v))]
        if bad:
            raise ValueError(f"variety memory: unknown dislike values {bad}")
        doc = self._load(user, subject)
        for axis, vals in avoid.items():
            merged = [v for v in doc["dislikes"].get(axis, []) if v not in vals] + list(dict.fromkeys(vals))
            doc["dislikes"][axis] = merged[-MAX_DISLIKES_PER_AXIS:]
        self._save(user, subject, doc)

    def forget(self, user):
        """Delete everything stored for one user (all subjects)."""
        shutil.rmtree(self._dir(user), ignore_errors=True)
