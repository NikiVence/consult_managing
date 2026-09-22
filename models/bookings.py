"""Запись связывает объекты студента и консультации."""

from datetime import datetime, timedelta

from .consultations import Consultation
from .users import Student


class Booking:
    """Запись с управляемым состоянием отмены."""

    def __init__(
        self,
        booking_id: int,
        student: Student,
        consultation: Consultation,
        duration_minutes: int,
        is_cancelled: bool = False,
    ) -> None:
        if type(booking_id) is not int or booking_id <= 0:
            raise ValueError("ID записи должен быть положительным целым числом.")
        if not isinstance(student, Student):
            raise ValueError("Записаться на консультацию может студент.")
        if not isinstance(consultation, Consultation):
            raise ValueError("Необходимо указать объект консультации.")
        consultation.validate_duration(duration_minutes)
        if type(is_cancelled) is not bool:
            raise ValueError("Признак отмены должен быть логическим значением.")
        self.id = booking_id
        self.student = student
        self.consultation = consultation
        self.duration_minutes = duration_minutes
        self._is_cancelled = is_cancelled

    @property
    def is_cancelled(self) -> bool:
        return self._is_cancelled

    @property
    def ends_at(self) -> datetime:
        return self.consultation.starts_at + timedelta(minutes=self.duration_minutes)

    @property
    def status(self) -> str:
        return "Отменена" if self.is_cancelled else "Подтверждена"

    def cancel(self) -> None:
        """Отменить запись; повторная отмена безопасна."""
        self._is_cancelled = True

    def confirmation(self) -> str:
        return (
            f"Запись #{self.id}: {self.status}\n"
            f"Студент: {self.student.name}\n"
            f"Преподаватель: {self.consultation.teacher.name}\n"
            f"Тема: {self.consultation.topic}\n"
            f"Начало: {self.consultation.starts_at:%d.%m.%Y %H:%M}\n"
            f"Окончание: {self.ends_at:%d.%m.%Y %H:%M}\n"
            f"Длительность: {self.duration_minutes} мин. "
            f"({self.duration_minutes / 60:.2f} ч.)"
        )

    def __str__(self) -> str:
        return (
            f"#{self.id} | {self.student.name} | "
            f"{self.consultation.topic} | {self.status}"
        )
