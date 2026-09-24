"""Farm worker container (phase 6 runs it). Carry-forward from the phase-1 review: a hard memory
cap and NO network. An upload is untrusted: the job's inputs are mounted read-only at /job and
the only writable host path is the job's own output dir at /out.

The container does not bound wall-clock time: the host (phase 6's worker) enforces the render
timeout and kills the container. `--init` makes that kill reap Blender and its children."""
import posixpath

ULIMIT_NOFILE = "4096:4096"


def _job_path(job_dir, farm_root):
    """The Linux-side job dir, validated: absolute, normalised, strictly under the farm root, and
    free of the ':' and ',' that would split or extend a docker mount spec."""
    if not isinstance(job_dir, str) or not posixpath.isabs(job_dir):
        raise ValueError(f"job dir must be an absolute Linux path: {job_dir!r}")
    if not posixpath.isabs(farm_root):
        raise ValueError(f"farm root must be an absolute Linux path: {farm_root!r}")
    if ":" in job_dir or "," in job_dir:
        raise ValueError(f"job dir must not contain ':' or ',': {job_dir!r}")
    root, path = posixpath.normpath(farm_root), posixpath.normpath(job_dir)
    if posixpath.commonpath([root, path]) != root or path == root:
        raise ValueError(f"job dir {job_dir!r} is not inside the farm root {farm_root!r}")
    return path


def container_argv(image, job_dir, *, farm_root, memory_gb=24, cpus=8, gpus="all", pids=512):
    job = _job_path(job_dir, farm_root)
    return ["docker", "run", "--rm", "--init",
            "--network=none",
            f"--memory={memory_gb}g", f"--memory-swap={memory_gb}g",
            f"--cpus={cpus}", f"--pids-limit={pids}", "--ulimit", f"nofile={ULIMIT_NOFILE}",
            "--read-only", "--tmpfs", "/tmp:rw,size=4g",
            "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--user", "1000:1000", f"--gpus={gpus}",
            "--mount", f"type=bind,source={job}/in,target=/job,readonly",
            "--mount", f"type=bind,source={job}/out,target=/out",
            image]
