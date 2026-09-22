"""Пользователи: наследование и полиморфное представление ролей."""


class User:
    """Общие данные пользователя системы."""

    role = "Пользователь"

    def __init__(self, user_id: int, name: str) -> None:
        if type(user_id) is not int or user_id <= 0:
            raise ValueError("ID пользователя должен быть положительным целым числом.")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Имя пользователя не должно быть пустым.")
        self.id = user_id
        self.name = name.strip()

    def __str__(self) -> str:
        return f"{self.role} #{self.id}: {self.name}"


class Student(User):
    """Студент, который записывается на консультации."""

    role = "Студент"

    def __str__(self) -> str:
        return f"{super().__str__()} (запись на консультации)"


class Teacher(User):
    """Преподаватель, который проводит консультации."""

    role = "Преподаватель"

    def __str__(self) -> str:
        return f"{super().__str__()} (проведение консультаций)"
