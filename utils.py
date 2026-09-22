"""Проверка консольного ввода."""

from datetime import datetime


def input_int(prompt: str) -> int:
    try:
        return int(input(prompt).strip())
    except ValueError as error:
        raise ValueError("Введите целое число.") from error


def input_datetime(prompt: str) -> datetime:
    try:
        return datetime.strptime(input(prompt).strip(), "%d.%m.%Y %H:%M")
    except ValueError as error:
        raise ValueError("Дата должна иметь вид ДД.ММ.ГГГГ ЧЧ:ММ.") from error
