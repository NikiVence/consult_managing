"""JSON: восстановление связей, валидация и защита при ошибке сохранения."""

import json
from datetime import datetime

import pytest

from models import Booking, Consultation, Student, Teacher
from storage import load_data, save_data


@pytest.fixture
def data():
    student = Student(1, "Никита")
    teacher = Teacher(2, "Иванова")
    consultation = Consultation(1, teacher, "Python", datetime(2026, 9, 16, 15))
    booking = Booking(1, student, consultation, 45)
    booking.cancel()
    return [student, teacher], [consultation], [booking]


def test_roundtrip_and_identity(tmp_path, data):
    path = tmp_path / "nested" / "data.json"
    save_data(path, data)
    users, consultations, bookings = load_data(path)
    assert isinstance(users[0], Student)
    assert isinstance(users[1], Teacher)
    assert consultations[0].teacher is users[1]
    assert bookings[0].student is users[0]
    assert bookings[0].consultation is consultations[0]
    assert bookings[0].is_cancelled
    assert "Никита" in path.read_text(encoding="utf-8")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["bookings"][0]["student_id"] == 1


def test_missing_file(tmp_path):
    assert load_data(tmp_path / "missing.json") == ([], [], [])


@pytest.mark.parametrize("text", ["bad", "[]", "{}", '{"version": 99}', "null"])
def test_invalid_json(tmp_path, text):
    path = tmp_path / "data.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="Некорректная база"):
        load_data(path)
    assert path.read_text(encoding="utf-8") == text


@pytest.mark.parametrize(
    "problem", ["reference", "duplicate", "role", "cancel", "conflict"]
)
def test_invalid_relations(tmp_path, data, problem):
    path = tmp_path / "data.json"
    save_data(path, data)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if problem == "reference":
        payload["bookings"][0]["student_id"] = 99
    elif problem == "duplicate":
        payload["users"].append(payload["users"][0])
    elif problem == "role":
        payload["consultations"][0]["teacher_id"] = 1
    elif problem == "cancel":
        payload["bookings"][0]["is_cancelled"] = "false"
    else:
        payload["bookings"][0]["is_cancelled"] = False
        payload["bookings"].append(dict(payload["bookings"][0], id=2))
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_data(path)


def test_failed_replace_preserves_file(monkeypatch, tmp_path, data):
    path = tmp_path / "data.json"
    save_data(path, data)
    original = path.read_bytes()

    def fail(*args):
        raise OSError("Нет доступа")

    monkeypatch.setattr("storage.os.replace", fail)
    with pytest.raises(OSError):
        save_data(path, ([], [], []))
    assert path.read_bytes() == original
    assert list(tmp_path.glob("*.tmp")) == []


def test_invalid_save_preserves_file(tmp_path, data):
    path = tmp_path / "data.json"
    save_data(path, data)
    original = path.read_bytes()
    with pytest.raises(ValueError):
        save_data(path, ([], data[1], data[2]))
    assert path.read_bytes() == original
