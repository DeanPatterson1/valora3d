"""One bake at a time on this machine: an exclusive OS lock on var/bake/.lock.

The OS lock (msvcrt on Windows, fcntl elsewhere) is released by the kernel when the holder dies, so a
crashed bake can never wedge the lock; the pid written into the file only names the holder in the
LockBusy message. A lock file left by a dead process is simply taken over and its pid rewritten.
The locked byte sits far past the pid text so other processes can still read who holds the lock.

The holder also records its Blender bake child (note_child). A child outlives a killed holder, so the next
holder reclaims it: a dead holder's still-running Blender child is killed before the next bake (_reclaim)."""
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = ROOT / "var" / "bake" / ".lock"
_LOCK_OFFSET = 1 << 20            # lock a byte beyond the pid text, never the text itself
_POLL_S = 0.05


class LockBusy(RuntimeError):
    pass


def _pid_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        h = k32.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            code = wintypes.DWORD()
            ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
            return bool(ok) and code.value == 259         # STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(pid, 0)                                   # POSIX only: signal 0 just probes
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _try_lock(fd):
    if sys.platform == "win32":
        import msvcrt
        os.lseek(fd, _LOCK_OFFSET, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    import fcntl
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(fd):
    if sys.platform == "win32":
        import msvcrt
        os.lseek(fd, _LOCK_OFFSET, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_UN)


def _holder(path):
    try:
        return int(Path(path).read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def _recorded_child(path):
    """The bake child pid a holder recorded with note_child ("child <pid>" on line 2), or None."""
    try:
        for line in Path(path).read_text().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "child":
                return int(parts[1])
    except (OSError, ValueError):
        pass
    return None


def _image_name(pid):
    """The executable's base name for a live pid (lower case), or "" when it cannot be read."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        h = k32.OpenProcess(0x1000, False, pid)
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            n = wintypes.DWORD(len(buf))
            if not k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
                return ""
            return Path(buf.value).name.lower()
        finally:
            k32.CloseHandle(h)
    try:
        return Path(os.readlink(f"/proc/{pid}/exe")).name.lower()
    except OSError:
        return ""


def _is_bake_child(pid):
    """Only a Blender process is ever reclaimed: a recorded pid may have been reused by anything else."""
    return _pid_alive(pid) and _image_name(pid).startswith("blender")


def _kill(pid):
    if sys.platform == "win32":
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        h = k32.OpenProcess(0x0001 | 0x00100000, False, pid)     # PROCESS_TERMINATE | SYNCHRONIZE
        if h:
            try:
                k32.TerminateProcess(h, 1)
                k32.WaitForSingleObject(h, 10000)
            finally:
                k32.CloseHandle(h)
        return
    import signal
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


def _reclaim(path):
    """Stale-lock reclaim, run right after the OS lock is taken. The kernel already freed the lock when its
    holder died, but that holder's Blender bake child can outlive it: an orphan still simulating (CPU and RAM)
    into a temp folder nobody will ever commit. When the recorded holder is dead and its recorded child is a
    live Blender, kill the child before the next bake starts. Returns the reclaimed child pid, or None."""
    holder, child = _holder(path), _recorded_child(path)
    if child is None or holder is None or _pid_alive(holder) or not _is_bake_child(child):
        return None
    _kill(child)
    return child


def note_child(pid, path=None):
    """The lock holder records its bake child (line 2 of the lock file), so a later holder can reclaim an
    orphan if this process dies first (_reclaim). Written only while this process holds the lock."""
    path = Path(path) if path is not None else LOCK_PATH
    try:
        holder = _holder(path)
        with open(path, "r+b") as f:
            f.seek(0)
            f.truncate()
            f.write(f"{holder if holder is not None else os.getpid()}\nchild {int(pid)}\n".encode())
    except OSError:
        pass


@contextmanager
def machine_lock(timeout_s=3600.0, path=None):
    """Hold the machine-wide bake lock for the with-block. Raises LockBusy after timeout_s."""
    path = Path(path) if path is not None else LOCK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        deadline = time.monotonic() + max(0.0, float(timeout_s))
        while not _try_lock(fd):
            if time.monotonic() >= deadline:
                pid = _holder(path)
                state = "alive" if _pid_alive(pid) else "not running (a child may hold its handle)"
                raise LockBusy(f"bake lock {path} is held by pid {pid} ({state}); one bake at a time")
            time.sleep(_POLL_S)
        _reclaim(path)
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n".encode())
        try:
            yield path
        finally:
            _unlock(fd)
    finally:
        os.close(fd)
