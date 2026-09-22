"""Проверки консольных сценариев после перехода к объектной модели."""

import pytest

from main import main
from storage import load_data


def run_menu(monkeypatch, path, answers):
    values = iter(answers)
    monkeypatch.setattr("builtins.input", lambda prompt: next(values))
    main(path)


def test_booking_survives_restart(monkeypatch, tmp_path, capsys):
    path = tmp_path / "data.json"
    run_menu(monkeypatch, path, ["7", "1", "1", "45", "0"])
    output = capsys.readouterr().out
    assert "Подтверждена" in output
    assert "45 мин. (0.75 ч.)" in output
    assert len(load_data(path)[2]) == 1
    run_menu(monkeypatch, path, ["8", "6", "1", "0"])
    output = capsys.readouterr().out
    assert "Алиев Никита" in output
    assert "Слот занят." in output


@pytest.mark.parametrize("duration", ["abc", "", "15.5", "-15", "²", "91", "9" * 5000])
def test_invalid_duration(monkeypatch, tmp_path, capsys, duration):
    path = tmp_path / "data.json"
    run_menu(monkeypatch, path, ["7", "1", "1", duration, "0"])
    assert "Ошибка:" in capsys.readouterr().out
    assert load_data(path)[2] == []


def test_empty_name(monkeypatch, tmp_path, capsys):
    path = tmp_path / "data.json"
    run_menu(monkeypatch, path, ["4", "1", "   ", "0"])
    assert "не должно быть пустым" in capsys.readouterr().out
    assert len(load_data(path)[0]) == 2


def test_menu_cancel_rebook_and_search(monkeypatch, tmp_path, capsys):
    path = tmp_path / "data.json"
    run_menu(
        monkeypatch,
        path,
        [
            "1",
            "2",
            "ооп",
            "3",
            "7",
            "1",
            "2",
            "45",
            "9",
            "1",
            "7",
            "1",
            "2",
            "30",
            "0",
        ],
    )
    output = capsys.readouterr().out
    assert "ООП в Python" in output
    bookings = load_data(path)[2]
    assert len(bookings) == 2
    assert bookings[0].is_cancelled
    assert not bookings[1].is_cancelled


def test_add_user_and_consultation(monkeypatch, tmp_path):
    path = tmp_path / "data.json"
    run_menu(
        monkeypatch,
        path,
        [
            "4",
            "2",
            "Петров",
            "5",
            "3",
            "Django",
            "01.01.2099 12:00",
            "0",
        ],
    )
    users, consultations, _ = load_data(path)
    assert consultations[-1].teacher is users[-1]
    assert consultations[-1].topic == "Django"


def test_corrupt_file_not_overwritten(tmp_path, capsys):
    path = tmp_path / "data.json"
    path.write_text("broken", encoding="utf-8")
    main(path)
    assert "Не удалось загрузить" in capsys.readouterr().out
    assert path.read_text(encoding="utf-8") == "broken"


def test_save_failure_rolls_back(monkeypatch, tmp_path, capsys):
    path = tmp_path / "data.json"
    run_menu(monkeypatch, path, ["0"])

    def fail_save(*args):
        raise OSError("Диск недоступен")

    monkeypatch.setattr("main.save_data", fail_save)
    run_menu(monkeypatch, path, ["7", "1", "1", "45", "8", "0"])
    output = capsys.readouterr().out
    assert "Диск недоступен" in output
    assert "Записей нет." in output
    assert load_data(path)[2] == []


def test_eof_exits_cleanly(monkeypatch, tmp_path, capsys):
    def end_input(prompt):
        raise EOFError

    monkeypatch.setattr("builtins.input", end_input)
    main(tmp_path / "data.json")
    assert "Работа завершена" in capsys.readouterr().out
