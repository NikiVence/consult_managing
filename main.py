"""ПР3: консольное меню системы управления консультациями."""

from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

from models import Consultation, Student, Teacher
from services import (
    create_booking,
    find_by_id,
    is_available,
    next_id,
    search_consultations,
    sort_consultations,
)
from storage import Data, load_data, save_data
from utils import input_datetime, input_int

DATA_PATH = Path(__file__).resolve().parent / "data" / "consultations.json"
MENU = """
1 — Расписание консультаций
2 — Поиск по теме или преподавателю
3 — Пользователи
4 — Добавить пользователя
5 — Добавить консультацию
6 — Проверить возможность записи
7 — Записать студента
8 — Все записи
9 — Отменить запись
0 — Выход
"""


def initial_data() -> Data:
    """Начальные объекты для первого запуска; далее загружается JSON."""
    student = Student(1, "Алиев Никита")
    teacher = Teacher(2, "Иванова Анна Сергеевна")
    tomorrow = (datetime.now() + timedelta(days=1)).replace(
        hour=15, minute=0, second=0, microsecond=0
    )
    consultations = [
        Consultation(1, teacher, "Основы Python", tomorrow),
        Consultation(2, teacher, "ООП в Python", tomorrow + timedelta(hours=2)),
    ]
    return [student, teacher], consultations, []


def execute_action(choice: str, data: Data) -> tuple[bool, str]:
    """Обработать действие; вернуть признак изменения и сообщение."""
    users, consultations, bookings = data
    if choice == "1":
        return False, "\n".join(str(item) for item in sort_consultations(consultations))
    if choice == "2":
        found = search_consultations(consultations, input("Тема или преподаватель: "))
        return False, "\n".join(str(item) for item in found) or "Ничего не найдено."
    if choice == "3":
        return False, "\n".join(str(user) for user in users) or "Пользователей нет."
    if choice == "4":
        role = input("Роль: 1 — студент, 2 — преподаватель: ").strip()
        if role not in ("1", "2"):
            raise ValueError("Выберите роль 1 или 2.")
        user_type = Student if role == "1" else Teacher
        user = user_type(next_id(users), input("Имя: "))
        users.append(user)
        return True, f"Добавлен: {user}"
    if choice == "5":
        teacher = find_by_id(users, input_int("ID преподавателя: "))
        topic = input("Тема: ")
        starts_at = input_datetime("Начало (ДД.ММ.ГГГГ ЧЧ:ММ): ")
        consultation = Consultation(next_id(consultations), teacher, topic, starts_at)
        if not consultation.is_future():
            raise ValueError("Укажите будущее время консультации.")
        if any(
            item.teacher.id == teacher.id and item.starts_at == starts_at
            for item in consultations
        ):
            raise ValueError("Такой слот преподавателя уже существует.")
        consultations.append(consultation)
        return True, f"Добавлена консультация: {consultation}"
    if choice == "6":
        consultation = find_by_id(consultations, input_int("ID консультации: "))
        if not consultation.is_future():
            return False, "Консультация уже началась или прошла."
        available = is_available(consultation, bookings)
        return False, "Слот свободен." if available else "Слот занят."
    if choice == "7":
        student = find_by_id(users, input_int("ID студента: "))
        consultation = find_by_id(consultations, input_int("ID консультации: "))
        duration = input_int("Длительность (15–90 минут): ")
        booking = create_booking(bookings, student, consultation, duration)
        return True, booking.confirmation()
    if choice == "8":
        return False, "\n".join(str(item) for item in bookings) or "Записей нет."
    if choice == "9":
        booking = find_by_id(bookings, input_int("ID записи: "))
        booking.cancel()
        return True, f"Запись #{booking.id} отменена. Слот освобождён."
    raise ValueError("Выберите пункт меню от 0 до 9.")


def main(data_path: Path = DATA_PATH) -> None:
    """Загрузить данные, выполнить меню, сохранять успешные изменения."""
    print("Система управления консультациями — ПР3")
    try:
        if data_path.exists():
            data = load_data(data_path)
        else:
            data = initial_data()
            save_data(data_path, data)
    except (OSError, ValueError) as error:
        print(f"Не удалось загрузить данные: {error}")
        return

    while True:
        try:
            print(MENU)
            choice = input("Выберите действие: ").strip()
            if choice == "0":
                print("Работа завершена. Данные сохранены.")
                return
            # Изменяем копию: ошибка записи файла не меняет рабочие объекты.
            draft = deepcopy(data)
            changed, message = execute_action(choice, draft)
            if changed:
                save_data(data_path, draft)
                data = draft
            print(message or "Консультаций нет.")
        except (ValueError, OSError) as error:
            print(f"Ошибка: {error}")
        except (EOFError, KeyboardInterrupt):
            print("\nРабота завершена. Успешные операции уже сохранены.")
            return


if __name__ == "__main__":
    main()
