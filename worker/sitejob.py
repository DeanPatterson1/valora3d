"""Driving `py -m engine.site_job run` as a subprocess: argv, the SITEJOB progress lines, the frame watcher, a hard
timeout that kills the whole process tree, and a scrubbed environment for the child."""
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from worker.contract import WorkerError

PREFIX = "SITEJOB "
STAGES = ("ingest", "direct", "render", "done", "error")
# Env the child may see. Everything else (RUNPOD_* job-reporting credentials above all) is withheld.
ENV_ALLOW = re.compile(r"^(PATH|HOME|LANG|LC_[A-Z]+|TZ|TMPDIR|TEMP|TMP|SYSTEMROOT|SystemRoot|USERPROFILE|APPDATA|"
                       r"LOCALAPPDATA|PYTHONPATH|PYTHONIOENCODING|PYTHONUNBUFFERED|LD_LIBRARY_PATH|BLENDER_EXE|"
                       r"VALORA_[A-Z0-9_]+|FAKE_SITEJOB_[A-Z_]+|ANTHROPIC_API_KEY|NVIDIA_[A-Z_]+|CUDA_[A-Z_]+|OCIO)$")
_BEAUTY = re.compile(r"^\d{4}\.png$")


def engine_dir():
    return Path(os.environ.get("VALORA_ENGINE_DIR") or Path(__file__).resolve().parents[1])


def site_job_cmd():
    """The command prefix for site_job; WORKER_SITE_JOB_CMD overrides it (local tests point it at the stub)."""
    raw = (os.environ.get("WORKER_SITE_JOB_CMD") or "").strip()
    if not raw:
        return [sys.executable, "-m", "engine.site_job"]
    if raw.startswith("["):                  # a JSON argv survives Windows paths and spaces
        return [str(x) for x in json.loads(raw)]
    return shlex.split(raw)


def child_env(extra=None):
    env = {k: v for k, v in os.environ.items() if ENV_ALLOW.match(k)}
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.update(extra or {})
    return env


_FEATURES = None


def features(cmd=None, cwd=None):
    """The long options `site_job run --help` lists (cached): lets the worker pass --markers the day the engine
    grows it, without a worker change."""
    global _FEATURES
    if _FEATURES is None or cmd is not None:
        try:
            out = subprocess.run([*(cmd or site_job_cmd()), "run", "--help"], capture_output=True, text=True,
                                 cwd=cwd or engine_dir(), env=child_env(), timeout=60).stdout
        except (OSError, subprocess.TimeoutExpired):
            out = ""
        found = frozenset(re.findall(r"(--[a-z][a-z0-9-]*)", out))
        if cmd is not None:
            return found
        _FEATURES = found
    return _FEATURES


def build_argv(params, model, out, *, timeout_s, provider, markers_file=None, feats=frozenset(), cmd=None):
    """site_job run argv for one job. `feats` gates optional flags the engine may not have yet."""
    argv = [*(cmd or site_job_cmd()), "run", "--model", str(model), "--out", str(out), "--tier", params.tier,
            "--provider", provider, "--timeout", str(int(timeout_s))]
    if params.prompt:
        argv += ["--prompt", params.prompt]
    if params.world:
        argv += ["--world", params.world]
    if params.aspect:
        argv += ["--aspect", params.aspect]
    if params.seed is not None:
        argv += ["--seed", str(params.seed)]
    if params.duration is not None:
        argv += ["--duration", f"{params.duration:g}"]
    if params.paint:
        argv += ["--paint", params.paint, "--finish", params.finish]
    if markers_file is not None and "--markers" in feats:
        argv += ["--markers", str(markers_file)]
    return argv


def parse_line(line):
    """'SITEJOB {json}' -> dict with a known 'stage'; anything else -> None (Blender chatter, warnings)."""
    line = line.strip()
    if not line.startswith(PREFIX):
        return None
    try:
        ev = json.loads(line[len(PREFIX):])
    except json.JSONDecodeError:
        return None
    if not isinstance(ev, dict) or ev.get("stage") not in STAGES:
        return None
    return ev


def count_beauty(beauty_dir):
    try:
        return sum(1 for e in os.scandir(beauty_dir) if _BEAUTY.match(e.name))
    except OSError:
        return 0


def _kill_tree(proc):
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=30)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.TimeoutExpired):
        proc.kill()


def run(argv, *, cwd, timeout_s, on_event, on_frames=None, poll_s=2.0, log_tail=200):
    """Run site_job, calling on_event(ev) per SITEJOB line and on_frames(done, total) as beauty frames appear.
    Returns (exit_code, last_event, stage, tail) where tail is the last `log_tail` non-SITEJOB lines.
    Raises WorkerError(RENDER_TIMEOUT) after timeout_s, having killed the process tree."""
    kw = {"start_new_session": True} if os.name != "nt" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    proc = subprocess.Popen(argv, cwd=cwd, env=child_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", bufsize=1, **kw)
    state = {"last": None, "stage": None, "beauty": None, "total": 0, "tail": []}
    done = threading.Event()

    def watch():
        seen = -1
        while not done.wait(poll_s):
            if state["beauty"] and on_frames:
                n = count_beauty(state["beauty"])
                if n != seen:
                    seen = n
                    on_frames(n, state["total"])

    def read():
        for line in proc.stdout:
            ev = parse_line(line)
            if ev is None:
                state["tail"].append(line.rstrip("\n"))
                del state["tail"][:-log_tail]
                continue
            state["last"] = ev
            if ev["stage"] != "error":
                state["stage"] = ev["stage"]
            if ev["stage"] == "render":
                state["beauty"] = ev.get("beauty")
                state["total"] = int(ev.get("frames") or 0)
            on_event(ev)

    watcher = threading.Thread(target=watch, daemon=True)
    reader = threading.Thread(target=read, daemon=True)
    watcher.start()
    reader.start()
    try:
        code = proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        proc.wait()
        raise WorkerError("RENDER_TIMEOUT", f"site_job ran past {int(timeout_s)} s (stage {state['stage']})")
    finally:
        if os.name != "nt":                   # no Blender outlives its job (the group dies with the leader)
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
        reader.join(timeout=10)
        done.set()
        watcher.join(timeout=5)
    return code, state["last"], state["stage"], state["tail"]
