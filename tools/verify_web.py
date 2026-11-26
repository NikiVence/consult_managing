"""Save repeatable local verification results without exposing environment secrets."""

from pathlib import Path
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
out = root / "docs/framework_pr5_7/evidence"
out.mkdir(parents=True, exist_ok=True)
checks = [
    (
        "django_tests",
        [sys.executable, "webapp/manage.py", "test", "schedule", "--verbosity", "2"],
        {},
    ),
    ("legacy_tests", [sys.executable, "-m", "pytest", "-q"], {}),
    ("django_check", [sys.executable, "webapp/manage.py", "check"], {}),
    ("deploy_local", [sys.executable, "webapp/manage.py", "check", "--deploy"], {}),
    (
        "deploy_https_profile",
        [sys.executable, "webapp/manage.py", "check", "--deploy"],
        {"DJANGO_HTTPS": "1"},
    ),
]
summary = {}
for name, command, extra in checks:
    result = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8", **extra},
    )
    (out / (name + ".txt")).write_text(
        "$ " + " ".join(command) + "\n" + result.stdout + result.stderr,
        encoding="utf-8",
    )
    summary[name] = {"exit_code": result.returncode}
    print(name, result.returncode)
    if result.returncode:
        print(result.stdout + result.stderr)
(out / "verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
raise SystemExit(int(any(item["exit_code"] for item in summary.values())))
