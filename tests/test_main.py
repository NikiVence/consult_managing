"""Проверки сценария ПР1 и граничных условий записи."""

from datetime import datetime

import pytest

from main import (
    calculate_end_time,
    create_confirmation,
    get_booking_status,
    main,
)


@pytest.mark.parametrize("duration", [15, 45, 90])
def test_available_consultation(duration):
    assert get_booking_status(
        True, datetime(2026, 9, 16, 15), datetime(2026, 9, 15), duration
    ) == "Запись доступна."


def test_occupied_consultation():
    assert get_booking_status(
        False, datetime(2026, 9, 16, 15), datetime(2026, 9, 15), 45
    ) == "Отказ: выбранное время уже занято."


@pytest.mark.parametrize("hour", [14, 15])
def test_started_consultation(hour):
    assert get_booking_status(
        True, datetime(2026, 9, 16, hour), datetime(2026, 9, 16, 15), 45
    ) == "Отказ: консультация уже началась или прошла."


@pytest.mark.parametrize("duration", [-1, 0, 14, 91])
def test_invalid_duration(duration):
    assert get_booking_status(
        True, datetime(2026, 9, 16, 15), datetime(2026, 9, 15), duration
    ) == "Отказ: длительность должна быть от 15 до 90 минут."


def test_end_time():
    assert calculate_end_time(
        datetime(2026, 9, 16, 15), 45
    ) == datetime(2026, 9, 16, 15, 45)


def test_end_time_crosses_midnight():
    assert calculate_end_time(
        datetime(2026, 12, 31, 23, 30), 90
    ) == datetime(2027, 1, 1, 1)


def test_confirmation():
    result = create_confirmation(
        "Анна", "Иванова", "Python",
        datetime(2026, 9, 16, 15), datetime(2026, 9, 16, 15, 45)
    )
    assert "Студент: Анна" in result
    assert "Преподаватель: Иванова" in result
    assert "Тема: Python" in result
    assert "Начало: 16.09.2026 15:00" in result
    assert "Окончание: 16.09.2026 15:45" in result


def test_successful_console_booking(monkeypatch, capsys):
    answers = iter(["  Анна  ", "45"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    main()
    output = capsys.readouterr().out
    assert "Запись подтверждена!" in output
    assert "Студент: Анна\n" in output
    assert "45 мин. (0.75 ч.)" in output
    assert "Слот свободен: False" in output


def test_empty_name(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda prompt: "   ")
    main()
    assert "имя студента не должно быть пустым" in capsys.readouterr().out


@pytest.mark.parametrize("duration", ["abc", "", "15.5", "-15", "²", "9" * 5000])
def test_invalid_console_input(monkeypatch, capsys, duration):
    answers = iter(["Анна", duration])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    main()
    output = capsys.readouterr().out
    assert "Отказ:" in output
    assert "Запись подтверждена!" not in output


def test_out_of_range_console_input(monkeypatch, capsys):
    answers = iter(["Анна", "91"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    main()
    output = capsys.readouterr().out
    assert "длительность должна быть от 15 до 90 минут" in output
    assert "Запись подтверждена!" not in output
