"""Операции над коллекциями объектов остаются обычными функциями."""

from datetime import datetime
from typing import TypeVar

from models import Booking, Consultation, Student, User

Entity = TypeVar("Entity", User, Consultation, Booking)


def find_by_id(items: list[Entity], entity_id: int) -> Entity:
    if type(entity_id) is not int or entity_id <= 0:
        raise ValueError("ID должен быть положительным целым числом.")
    for item in items:
        if item.id == entity_id:
            return item
    raise ValueError(f"Объект с ID {entity_id} не найден.")


def next_id(items: list[Entity]) -> int:
    return max((item.id for item in items), default=0) + 1


def search_consultations(
    consultations: list[Consultation],
    query: str,
) -> list[Consultation]:
    query = query.strip().casefold()
    return [
        item
        for item in consultations
        if query in item.topic.casefold() or query in item.teacher.name.casefold()
    ]


def sort_consultations(consultations: list[Consultation]) -> list[Consultation]:
    return sorted(consultations, key=lambda item: (item.starts_at, item.id))


def is_available(consultation: Consultation, bookings: list[Booking]) -> bool:
    """Проверить занятость слота; дату проверяет Consultation.is_future()."""
    return not any(
        booking.consultation.id == consultation.id and not booking.is_cancelled
        for booking in bookings
    )


def bookings_conflict(first: Booking, second: Booking) -> bool:
    if first.is_cancelled or second.is_cancelled:
        return False
    if first.consultation.id == second.consultation.id:
        return True
    same_person = (
        first.student.id == second.student.id
        or first.consultation.teacher.id == second.consultation.teacher.id
    )
    overlap = (
        first.consultation.starts_at < second.ends_at
        and second.consultation.starts_at < first.ends_at
    )
    return same_person and overlap


def create_booking(
    bookings: list[Booking],
    student: Student,
    consultation: Consultation,
    duration_minutes: int,
    now: datetime | None = None,
) -> Booking:
    """Создать запись только после проверки даты, слота и пересечений."""
    if not consultation.is_future(now):
        raise ValueError("Консультация уже началась или прошла.")
    if not is_available(consultation, bookings):
        raise ValueError("Выбранное время уже занято.")
    booking = Booking(next_id(bookings), student, consultation, duration_minutes)
    if any(bookings_conflict(booking, existing) for existing in bookings):
        raise ValueError("У студента или преподавателя уже есть запись на это время.")
    bookings.append(booking)
    return booking
