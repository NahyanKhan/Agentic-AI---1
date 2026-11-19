"""Execute generated assertions in a resource-limited, networkless Docker container."""

from __future__ import annotations

import shutil
import subprocess

SANDBOX_IMAGE = "python:3.12-alpine"


def run_cases(code: str, cases: list[dict], timeout: float = 20.0) -> dict:
    """Run code and assertions inside a disposable, read-only, no-network container."""
    if not cases:
        return {"passed": False, "returncode": None, "stdout": "", "stderr": "The test writer did not return any tests.", "timed_out": False}
    if len(code) > 100_000 or sum(len(str(case.get("assertion", ""))) for case in cases) > 16_000:
        return {"passed": False, "returncode": None, "stdout": "", "stderr": "The code or generated tests exceed the sandbox input limit.", "timed_out": False}

    docker = shutil.which("docker")
    if not docker:
        return {
            "passed": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"Docker is required for isolated test execution. Install and start Docker Desktop, then run `docker pull {SANDBOX_IMAGE}` once.",
            "timed_out": False,
        }

    try:
        image = subprocess.run([docker, "image", "inspect", SANDBOX_IMAGE], capture_output=True, text=True, timeout=5, check=False)
    except subprocess.TimeoutExpired:
        return {"passed": False, "returncode": None, "stdout": "", "stderr": "Docker is not responding. Ensure Docker Desktop is started and ready.", "timed_out": True}
    except OSError as exc:
        return {"passed": False, "returncode": None, "stdout": "", "stderr": f"Could not check Docker: {exc}", "timed_out": False}

    if image.returncode != 0:
        docker_message = (image.stderr or "").lower()
        if any(marker in docker_message for marker in (
            "cannot connect", "is the docker daemon running", "error during connect",
            "failed to connect", "dockerdesktoplinuxengine", "connection refused",
            "daemon is not running", "not running", "pipe"
        )):
            return {
                "passed": False,
                "returncode": None,
                "stdout": "",
                "stderr": "Docker Desktop is installed but not running. Start Docker Desktop, wait for the engine to be ready, and retry.",
                "timed_out": False,
            }
        return {
            "passed": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"Sandbox image is not installed. Run `docker pull {SANDBOX_IMAGE}` once in your terminal, then try again.",
            "timed_out": False,
        }

    assertions = "\n".join(str(case.get("assertion", "")) for case in cases)
    harness = code + "\n\n# Generated behavior checks\n" + assertions + "\nprint('All generated tests passed.')\n"
    command = [
        docker, "run", "--pull=never", "--rm", "-i", "--network=none", "--read-only",
        "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=64",
        "--memory=192m", "--memory-swap=192m", "--cpus=0.5", "--user=65534:65534",
        "--ulimit", "cpu=10:10", "--ulimit", "nofile=64:64",
        "--ulimit", "fsize=8388608:8388608", "--ulimit", "core=0:0",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m", SANDBOX_IMAGE,
        "python", "-I", "-",
    ]
    try:
        result = subprocess.run(command, input=harness, capture_output=True, text=True, timeout=timeout, check=False)
        return {
            "passed": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {"passed": False, "returncode": None, "stdout": str(exc.stdout or "")[-4000:], "stderr": "Sandbox execution timed out.", "timed_out": True}
    except OSError as exc:
        return {"passed": False, "returncode": None, "stdout": "", "stderr": f"Could not start Docker sandbox: {exc}", "timed_out": False}
