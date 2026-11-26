"""Create a PostgreSQL custom-format backup without passing passwords on argv."""

from datetime import datetime
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent.parent
folder = root / ".runtime/backups"
folder.mkdir(parents=True, exist_ok=True)
target = folder / (
    "consultations-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".dump"
)
with target.open("wb") as output:
    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            "pg_dump",
            "-U",
            "consultations",
            "-d",
            "consultations",
            "-Fc",
        ],
        cwd=root,
        stdout=output,
        check=True,
    )
print(target)
