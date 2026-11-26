"""Generate local secrets once; never replace existing credentials."""

from pathlib import Path
import secrets

root = Path(__file__).resolve().parent.parent
path = root / ".env"
if path.exists():
    existing = path.read_text(encoding="utf-8")
    if "POSTGRES_ADMIN_PASSWORD=" not in existing:
        with path.open("a", encoding="utf-8") as output:
            output.write(f"\nPOSTGRES_ADMIN_PASSWORD={secrets.token_urlsafe(32)}\n")
    print(".env already exists; keeping its settings.")
else:
    student = secrets.token_urlsafe(14)
    teacher = secrets.token_urlsafe(14)
    path.write_text(
        f"DJANGO_SECRET_KEY={secrets.token_urlsafe(64)}\n"
        f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n"
        f"POSTGRES_ADMIN_PASSWORD={secrets.token_urlsafe(32)}\n"
        "POSTGRES_USER=consultations\nPOSTGRES_DB=consultations\n"
        "DJANGO_DEBUG=0\nDJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver\n"
        f"DEMO_STUDENT_PASSWORD={student}\nDEMO_TEACHER_PASSWORD={teacher}\n",
        encoding="utf-8",
    )
    folder = root / ".runtime"
    folder.mkdir(exist_ok=True)
    (folder / "demo_accounts.txt").write_text(
        "Локальный учебный стенд: http://127.0.0.1:8088\n"
        f"Студент: student\nПароль: {student}\n\n"
        f"Преподаватель: teacher\nПароль: {teacher}\n",
        encoding="utf-8",
    )
    print("Created .env and .runtime/demo_accounts.txt (both excluded from Git).")
