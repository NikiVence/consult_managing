"""Прежние проверки правил записи и новые проверки объектной модели."""

from datetime import datetime, timedelta

import pytest

from models import Booking, Consultation, Student, Teacher, User
from services import (
    create_booking,
    find_by_id,
    is_available,
    search_consultations,
    sort_consultations,
)

NOW = datetime(2026, 9, 22, 12)


@pytest.fixture
def consultation():
    return Consultation(1, Teacher(2, "Иванова"), "Python", NOW + timedelta(days=1))


def test_users_and_polymorphism():
    student = Student(1, "  Никита  ")
    teacher = Teacher(2, "Иванова")
    assert isinstance(student, User)
    assert isinstance(teacher, User)
    assert student.name == "Никита"
    assert str(student) == "Студент #1: Никита (запись на консультации)"
    assert str(teacher) == "Преподаватель #2: Иванова (проведение консультаций)"


@pytest.mark.parametrize("user_id,name", [(0, "А"), (True, "А"), (1, " "), (1, None)])
def test_invalid_user(user_id, name):
    with pytest.raises(ValueError):
        Student(user_id, name)


@pytest.mark.parametrize("duration", [15, 45, 90])
def test_booking_and_confirmation(consultation, duration):
    student = Student(1, "Никита")
    bookings = []
    booking = create_booking(bookings, student, consultation, duration, NOW)
    assert booking.student is student
    assert booking.consultation is consultation
    assert booking.ends_at == consultation.starts_at + timedelta(minutes=duration)
    assert "Студент: Никита" in booking.confirmation()
    assert "Преподаватель: Иванова" in booking.confirmation()
    assert "Тема: Python" in booking.confirmation()
    assert booking.status == "Подтверждена"
    assert not is_available(consultation, bookings)


@pytest.mark.parametrize("duration", [-1, 0, 14, 91, 15.5, True, "45"])
def test_invalid_duration(consultation, duration):
    bookings = []
    with pytest.raises(ValueError):
        create_booking(bookings, Student(1, "Никита"), consultation, duration, NOW)
    assert bookings == []


@pytest.mark.parametrize("offset", [-1, 0])
def test_started_consultation(consultation, offset):
    consultation.starts_at = NOW + timedelta(minutes=offset)
    with pytest.raises(ValueError, match="началась"):
        create_booking([], Student(1, "Никита"), consultation, 45, NOW)


def test_double_booking_cancel_and_rebook(consultation):
    bookings = []
    student = Student(1, "Никита")
    first = create_booking(bookings, student, consultation, 45, NOW)
    with pytest.raises(ValueError, match="занято"):
        create_booking(bookings, Student(3, "Анна"), consultation, 30, NOW)
    first.cancel()
    first.cancel()
    assert first.status == "Отменена"
    assert is_available(consultation, bookings)
    second = create_booking(bookings, student, consultation, 30, NOW)
    assert second.id == 2
    assert len(bookings) == 2


def test_cancel_state_is_read_only(consultation):
    booking = Booking(1, Student(1, "Никита"), consultation, 45)
    with pytest.raises(AttributeError):
        booking.is_cancelled = True


def test_end_time_crosses_year(consultation):
    consultation.starts_at = datetime(2026, 12, 31, 23, 30)
    booking = Booking(1, Student(1, "Никита"), consultation, 90)
    assert booking.ends_at == datetime(2027, 1, 1, 1)


@pytest.mark.parametrize("shared_person", ["student", "teacher"])
def test_overlapping_bookings(consultation, shared_person):
    student = Student(1, "Никита")
    bookings = []
    create_booking(bookings, student, consultation, 45, NOW)
    teacher = (
        consultation.teacher if shared_person == "teacher" else Teacher(4, "Петров")
    )
    other_student = student if shared_person == "student" else Student(3, "Анна")
    other = Consultation(
        2, teacher, "ООП", consultation.starts_at + timedelta(minutes=30)
    )
    with pytest.raises(ValueError, match="уже есть запись"):
        create_booking(bookings, other_student, other, 45, NOW)


def test_adjacent_bookings_allowed(consultation):
    student = Student(1, "Никита")
    bookings = []
    create_booking(bookings, student, consultation, 45, NOW)
    other = Consultation(
        2, consultation.teacher, "ООП", consultation.starts_at + timedelta(minutes=45)
    )
    create_booking(bookings, student, other, 15, NOW)
    assert len(bookings) == 2


def test_search_sort_and_find(consultation):
    earlier = Consultation(2, consultation.teacher, "ООП", NOW)
    items = [consultation, earlier]
    assert find_by_id(items, 1) is consultation
    assert search_consultations(items, "  PYTHON ") == [consultation]
    assert search_consultations(items, "иванова") == items
    assert sort_consultations(items) == [earlier, consultation]
    assert items[0] is consultation
    with pytest.raises(ValueError, match="не найден"):
        find_by_id(items, 99)


def test_wrong_role_rejected(consultation):
    with pytest.raises(ValueError):
        Consultation(2, Student(1, "Никита"), "Python", NOW)
    with pytest.raises(ValueError):
        Booking(1, consultation.teacher, consultation, 45)
