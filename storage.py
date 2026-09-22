"""JSON хранит идентификаторы связей, память — связанные объекты."""

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from models import Booking, Consultation, Student, Teacher, User
from services import bookings_conflict, find_by_id

Data = tuple[list[User], list[Consultation], list[Booking]]


def check_unique(items: list) -> None:
    ids = [item.id for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("Обнаружены повторяющиеся ID.")


def load_data(path: Path) -> Data:
    """Отсутствующий файл означает пустую базу; повреждённый — ошибку."""
    if not path.exists():
        return [], [], []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != 1:
            raise ValueError("Неизвестный формат базы данных.")
        for key in ("users", "consultations", "bookings"):
            if not isinstance(data[key], list):
                raise ValueError(f"Поле {key} должно быть списком.")
        user_types = {"Студент": Student, "Преподаватель": Teacher}
        users = [
            user_types[item["role"]](item["id"], item["name"]) for item in data["users"]
        ]
        check_unique(users)
        consultations = [
            Consultation(
                item["id"],
                find_by_id(users, item["teacher_id"]),
                item["topic"],
                datetime.fromisoformat(item["starts_at"]),
            )
            for item in data["consultations"]
        ]
        check_unique(consultations)
        bookings = [
            Booking(
                item["id"],
                find_by_id(users, item["student_id"]),
                find_by_id(consultations, item["consultation_id"]),
                item["duration_minutes"],
                item["is_cancelled"],
            )
            for item in data["bookings"]
        ]
        check_unique(bookings)
        for index, booking in enumerate(bookings):
            if any(bookings_conflict(booking, other) for other in bookings[:index]):
                raise ValueError("В базе найдены конфликтующие активные записи.")
        return users, consultations, bookings
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        raise ValueError(f"Некорректная база {path.name}: {error}") from error


def save_data(path: Path, data: Data) -> None:
    """Записать единый снимок через временный файл и атомарную замену."""
    users, consultations, bookings = data
    payload = {
        "version": 1,
        "users": [
            {"id": user.id, "name": user.name, "role": user.role} for user in users
        ],
        "consultations": [
            {
                "id": item.id,
                "teacher_id": item.teacher.id,
                "topic": item.topic,
                "starts_at": item.starts_at.isoformat(),
            }
            for item in consultations
        ],
        "bookings": [
            {
                "id": item.id,
                "student_id": item.student.id,
                "consultation_id": item.consultation.id,
                "duration_minutes": item.duration_minutes,
                "is_cancelled": item.is_cancelled,
            }
            for item in bookings
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary = Path(file.name)
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
        # Проверяем ссылки и данные до замены существующего файла.
        load_data(temporary)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
