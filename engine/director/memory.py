"""Variety memory (spec §6 layer 3): per user and per subject, the directions used and the values the
user disliked. Local files only (under var/, gitignored).
Privacy: users are identified only by tokens this server issues (random + HMAC-SHA256 tag keyed by a
server secret: VALORA_VARIETY_SECRET, at least 32 characters, required in production; only with
VALORA_VARIETY_DEV=1 (or dev=True) a 32-byte key file <root>/.secret is created on first use, owner-only:
chmod 0600 on POSIX, an owner-only DACL via icacls on Windows, verified before the key is trusted).
A fabricated or altered token is rejected. File and directory names are hashes
of the token and subject key, never raw input, so no path can escape the root. Every stored value is
validated (catalog values, id == its axes, source enum, numeric ranges), so no free text can reach a
file, and reads filter anything that does not look like a stored value. Files are bounded, writes are
atomic, a corrupt or oversized file reads as empty, and forget(user) serves deletion.
Concurrency: one lock per USER, kept outside the user's data directory (<root>/.locks/<hash>.lock, so
forget() can delete the data while holding it and never unlinks a live lock): an OS file lock (released
by the OS if the holder dies, so it is never broken while live) plus a refcounted in-process lock that
is dropped when nobody holds or waits for it, around read -> pick -> record and around forget().
Rotation: besides the bounded entry log, each subject keeps the last-use counter per direction id,
capped by the subject's catalog size, so a pool larger than the log still rotates fully before repeats. A lock that stays busy past
LOCK_TIMEOUT_S raises MemoryBusy; the caller then runs without memory (it never writes unlocked)."""
import contextlib
import datetime
import hashlib
import hmac
import json
import math
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

MEMORY_ENV, SECRET_ENV, DEV_ENV = "VALORA_VARIETY_DIR", "VALORA_VARIETY_SECRET", "VALORA_VARIETY_DEV"
MIN_SECRET_CHARS = 32
MAX_ROTATION = 2048        # (eng) hard cap on per-direction rotation state; the catalog size caps it first
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
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_THREAD_LOCKS, _THREAD_LOCKS_GUARD = {}, threading.Lock()
_RESTRICTED = set()        # key files verified owner-only in this process


class MemoryBusy(RuntimeError):
    pass


class SecretMissing(RuntimeError):
    """No server secret: set VALORA_VARIETY_SECRET (production) or VALORA_VARIETY_DEV=1 (local dev)."""


def _sys32(exe):
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", exe)


def _owner_only(path):
    """Restrict `path` to the current user and verify it; raises OSError when it cannot be verified."""
    if sys.platform != "win32":
        os.chmod(path, 0o600)
        if os.stat(path).st_mode & 0o077:
            raise OSError(f"could not make {path} owner-only")
        return
    import subprocess
    out = subprocess.run([_sys32("whoami.exe"), "/user", "/fo", "csv", "/nh"], capture_output=True, text=True,
                         check=True, timeout=30).stdout.strip()
    name, sid = [x.strip('"') for x in out.split('","')]
    subprocess.run([_sys32("icacls.exe"), str(path), "/inheritance:r", "/grant:r", f"*{sid}:F"],
                   capture_output=True, text=True, check=True, timeout=30)
    if _acl(path) not in ([name.lower()], [sid.lower()]):
        raise OSError(f"could not verify an owner-only ACL on {path}")


def _acl(path):
    """Windows: the principals of the ACEs on `path`, lower-case, as icacls lists them."""
    import subprocess
    out = subprocess.run([_sys32("icacls.exe"), str(path)], capture_output=True, text=True, check=True,
                         timeout=30).stdout
    lines = out.splitlines()
    first = lines[0][len(str(path)):] if lines and lines[0].startswith(str(path)) else ""
    aces = [first.strip()] + [ln.strip() for ln in lines[1:]]
    out = []
    for ace in aces:
        if not ace or ace.startswith("Successfully processed"):
            break
        out.append(ace.split(":(", 1)[0].lower())
    return out


def _acquire_thread_lock(key, timeout):
    """Refcounted per-key in-process lock: the entry lives while anyone holds OR waits for it."""
    with _THREAD_LOCKS_GUARD:
        entry = _THREAD_LOCKS.setdefault(key, [threading.Lock(), 0])
        entry[1] += 1
    if entry[0].acquire(timeout=timeout):
        return entry
    _drop_thread_lock(key, entry, held=False)
    raise MemoryBusy("variety memory is busy for this user")


def _drop_thread_lock(key, entry, held=True):
    if held:
        entry[0].release()
    with _THREAD_LOCKS_GUARD:
        entry[1] -= 1
        if entry[1] == 0 and _THREAD_LOCKS.get(key) is entry:
            del _THREAD_LOCKS[key]


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


def _entry(e):
    """A stored entry rebuilt from its validated fields, or None."""
    if not isinstance(e, dict) or not _stored_id(e.get("id")):
        return None
    seed, dur, src, day = e.get("seed"), e.get("durationS"), e.get("source"), e.get("day")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2 ** 31:
        return None
    if isinstance(dur, bool) or not isinstance(dur, (int, float)) or not 1 <= dur <= 60:
        return None
    if src not in SOURCES or not isinstance(day, str) or not _DAY.match(day):
        return None
    return {"id": e["id"], "seed": seed, "durationS": dur, "source": src, "day": day}


class VarietyMemory:
    def __init__(self, root=None, *, dev=False):
        """dev=True allows the local key file without VALORA_VARIETY_DEV (throwaway roots: tests, the
        offline harness)."""
        self.root = Path(root or os.environ.get(MEMORY_ENV) or DEFAULT_DIR)
        self.dev = dev
        self._secret = None

    def _key_bytes(self):
        if self._secret is not None:
            return self._secret
        env = os.environ.get(SECRET_ENV)
        if env:
            if len(env) < MIN_SECRET_CHARS:
                raise SecretMissing(f"{SECRET_ENV} must be at least {MIN_SECRET_CHARS} characters")
            self._secret = env.encode()
            return self._secret
        if not (self.dev or os.environ.get(DEV_ENV) == "1"):
            raise SecretMissing(f"set {SECRET_ENV} (at least {MIN_SECRET_CHARS} characters); a local key file "
                                f"is only created with {DEV_ENV}=1")
        p = self.root / ".secret"
        self.root.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            # Write the key fully under a temp name, restrict and verify it, then link it into place: a
            # concurrent reader sees either no file or all 32 bytes, and a losing writer keeps the winner's key.
            fd, tmp = tempfile.mkstemp(dir=self.root, prefix=".secret-", suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(secrets.token_bytes(SECRET_BYTES))
                _owner_only(tmp)
                with contextlib.suppress(FileExistsError):
                    os.link(tmp, p)
            finally:
                os.remove(tmp)
        elif str(p) not in _RESTRICTED:
            _owner_only(p)                               # an older or copied key file is re-restricted
        _RESTRICTED.add(str(p))                          # verified once per process (icacls is slow)
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

    def _lock_path(self, user):
        """Per-user lock, OUTSIDE the user's data directory (forget() deletes that directory)."""
        return self.root / ".locks" / f"{self._dir(user).name}.lock"

    def locked(self, user, subject):
        self._path(user, subject)                        # validates the token and the subject key
        return self._locked_user(user)

    @contextlib.contextmanager
    def _locked_user(self, user):
        p = self._lock_path(user)
        p.parent.mkdir(parents=True, exist_ok=True)
        timeout = LOCK_TIMEOUT_S
        deadline, wait = time.monotonic() + timeout, 0.01
        entry = _acquire_thread_lock(str(p), timeout)
        fd = None
        try:
            fd = os.open(p, os.O_CREAT | os.O_RDWR, 0o600)
            while True:
                try:
                    _oslock(fd)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise MemoryBusy("variety memory is busy for this user") from None
                    time.sleep(wait)
                    wait = min(wait * 2, 0.2)
            try:
                yield
            finally:
                _osunlock(fd)
        finally:
            if fd is not None:
                os.close(fd)
            _drop_thread_lock(str(p), entry)

    def _load(self, user, subject):
        """Rebuilt from validated fields only: unknown fields, bad values and junk ids are dropped."""
        p = self._path(user, subject)
        empty = {"entries": [], "dislikes": {}, "used": {}, "n": 0}
        try:
            if p.stat().st_size > MAX_FILE_BYTES:
                return empty
            doc = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(doc, dict) or not isinstance(doc.get("entries"), list)                     or not isinstance(doc.get("dislikes", {}), dict) or not isinstance(doc.get("used", {}), dict):
                return empty
        except (OSError, ValueError):
            return empty
        entries = [e for e in map(_entry, doc["entries"]) if e is not None]
        dislikes = {a: list(dict.fromkeys(v for v in vals if isinstance(v, str) and _VALUE.match(v)))
                    for a, vals in doc.get("dislikes", {}).items() if a in AXES and isinstance(vals, list)}
        used = {i: n for i, n in doc.get("used", {}).items()
                if _stored_id(i) and isinstance(n, int) and not isinstance(n, bool) and 0 < n < 2 ** 53}
        n = doc.get("n") if isinstance(doc.get("n"), int) and not isinstance(doc.get("n"), bool) else 0
        return {"entries": entries[-MAX_ENTRIES:],
                "dislikes": {a: v[-MAX_DISLIKES_PER_AXIS:] for a, v in dislikes.items() if v},
                "used": used, "n": max([n, 0] + list(used.values()))}

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
        """Every remembered direction id, least recently used first (the dice's history)."""
        used = self._load(user, subject)["used"]
        return sorted(used, key=lambda i: (used[i], i))

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
        doc["n"] += 1
        doc["used"][direction.id] = doc["n"]
        cap = min(MAX_ROTATION, math.prod(max(1, len(known.get(a, ()))) for a in AXES))
        if len(doc["used"]) > cap:                       # forget the least recently used first
            keep = sorted(doc["used"], key=lambda i: (-doc["used"][i], i))[:cap]
            doc["used"] = {i: doc["used"][i] for i in keep}
        self._save(user, subject, doc)

    def avoided(self, user, subject, known=None):
        """Stored dislikes; with `known` (this subject's catalog values) values no longer offered are dropped."""
        out = {a: list(v) for a, v in self._load(user, subject)["dislikes"].items()}
        if known is not None:
            out = {a: [x for x in v if x in known.get(a, ())] for a, v in out.items()}
        return {a: v for a, v in out.items() if v}

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
        """Delete everything stored for one user (all subjects), under the user's lock so no write races
        it. Failures are raised, never swallowed; a user with nothing stored is a no-op."""
        d = self._dir(user)
        with self._locked_user(user):
            try:
                shutil.rmtree(d)
            except FileNotFoundError:
                pass
            if d.exists():
                raise OSError(f"variety memory: could not delete {d.name}")
