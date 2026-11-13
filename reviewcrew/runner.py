"""Opt-in convenience runner. This is not a security sandbox."""

import os
import subprocess
import sys
import tempfile


def run_cases(code: str, cases: list[dict], timeout: float = 2.0) -> dict:
    """Run generated assertions in a temporary process with a short timeout."""
    harness = code + "\n\n" + "\n".join(c["assertion"] for c in cases)
    safe_env = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"}
    try:
        with tempfile.TemporaryDirectory(prefix="reviewcrew-") as folder:
            result = subprocess.run([sys.executable, "-I", "-c", harness], cwd=folder, env=safe_env, capture_output=True, text=True, timeout=timeout, check=False)
        return {"passed": result.returncode == 0, "returncode": result.returncode, "stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:], "timed_out": False}
    except subprocess.TimeoutExpired as exc:
        return {"passed": False, "returncode": None, "stdout": str(exc.stdout or "")[-4000:], "stderr": "Execution timed out.", "timed_out": True}
