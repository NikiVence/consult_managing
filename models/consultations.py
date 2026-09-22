"""Консультация преподавателя и правила длительности встречи."""

from datetime import datetime

from .users import Teacher


class Consultation:
    """Индивидуальный слот с началом и максимальной длительностью 90 минут."""

    MIN_DURATION = 15
    MAX_DURATION = 90

    def __init__(
        self,
        consultation_id: int,
        teacher: Teacher,
        topic: str,
        starts_at: datetime,
    ) -> None:
        if type(consultation_id) is not int or consultation_id <= 0:
            raise ValueError("ID консультации должен быть положительным целым числом.")
        if not isinstance(teacher, Teacher):
            raise ValueError("Консультацию должен проводить преподаватель.")
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError("Тема консультации не должна быть пустой.")
        if not isinstance(starts_at, datetime) or starts_at.tzinfo is not None:
            raise ValueError("Укажите местные дату и время без часового пояса.")
        self.id = consultation_id
        self.teacher = teacher
        self.topic = topic.strip()
        self.starts_at = starts_at

    @staticmethod
    def validate_duration(duration_minutes: int) -> None:
        """Проверить длительность без создания экземпляра консультации."""
        if (
            type(duration_minutes) is not int
            or not Consultation.MIN_DURATION
            <= duration_minutes
            <= Consultation.MAX_DURATION
        ):
            raise ValueError("Длительность должна быть от 15 до 90 целых минут.")

    def is_future(self, now: datetime | None = None) -> bool:
        return self.starts_at > (now if now is not None else datetime.now())

    def __str__(self) -> str:
        return (
            f"#{self.id} | {self.topic} | {self.teacher.name} | "
            f"{self.starts_at:%d.%m.%Y %H:%M}"
        )
