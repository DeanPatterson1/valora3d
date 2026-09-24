"""Farm worker container (phase 6 runs it). Carry-forward from the phase-1 review: a hard memory
cap and NO network. An upload is untrusted; the job dir is the only thing mounted."""


def container_argv(image, job_dir, *, memory_gb=24, cpus=8, gpus="all", pids=512):
    return ["docker", "run", "--rm",
            "--network=none",
            f"--memory={memory_gb}g", f"--memory-swap={memory_gb}g",
            f"--cpus={cpus}", f"--pids-limit={pids}",
            "--read-only", "--tmpfs", "/tmp:rw,size=4g",
            "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--user", "1000:1000", f"--gpus={gpus}",
            "-v", f"{job_dir}:/job:rw",
            image]
