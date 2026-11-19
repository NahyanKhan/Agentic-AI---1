"""Run Ruff over pasted Python without executing it."""

import json
import subprocess
import sys

from reviewcrew.analyzer import Finding


def lint_python(code: str) -> tuple[list[Finding], str | None]:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--output-format=json", "--select", "E,F,I,N,B,UP", "--stdin-filename", "submitted.py", "-"],
            input=code,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return [], "Ruff style analysis timed out."
    except OSError:
        return [], "Ruff is unavailable; install the project requirements to enable the full style checks."

    if result.returncode not in (0, 1):
        return [], "Ruff could not analyze this snippet."
    if result.returncode == 1 and not result.stdout.strip():
        if "no module named ruff" in (result.stderr or "").lower():
            return [], "Ruff is not installed in the active Python environment. Run `pip install -r requirements.txt`."
        return [], "Ruff could not analyze this snippet."
    try:
        messages = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return [], "Ruff returned an unreadable result."

    findings = []
    for item in messages:
        code_id = (item.get("code") or "")
        message = item.get("message", "Style issue detected.")
        location = item.get("location") or {}
        end_location = item.get("end_location") or {}
        fix = item.get("fix") or {}
        suggestion = fix.get("message") or "Apply the matching Python lint convention."
        severity = "medium" if code_id.startswith(("F", "B")) else "low"
        category = "Correctness" if code_id.startswith(("F", "B")) else "Style"
        findings.append(Finding(severity, category, f"Ruff {code_id}: {message}", location.get("row"), suggestion))
    return findings, None
