"""One bake at a time on this machine: an exclusive OS lock on var/bake/.lock.

The OS lock (msvcrt on Windows, fcntl elsewhere) is released by the kernel when the holder dies, so a
crashed bake can never wedge the lock; the pid written into the file only names the holder in the
LockBusy message. A lock file left by a dead process is simply taken over and its pid rewritten.
The locked byte sits far past the pid text so other processes can still read who holds the lock."""
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
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n".encode())
        try:
            yield path
        finally:
            _unlock(fd)
    finally:
        os.close(fd)
