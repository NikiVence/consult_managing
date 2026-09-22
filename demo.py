"""Воспроизводимая демонстрация ПР3; пользовательская база не изменяется."""

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from models import Consultation, Student, Teacher
from services import create_booking, is_available
from storage import load_data, save_data


def main() -> None:
    now = datetime.now()
    starts_at = (now + timedelta(days=1)).replace(
        hour=15, minute=0, second=0, microsecond=0
    )
    student = Student(1, "Алиев Никита")
    teacher = Teacher(2, "Иванова Анна Сергеевна")
    consultation = Consultation(1, teacher, "ООП в Python", starts_at)
    bookings = []
    print("НАСЛЕДОВАНИЕ И ПОЛИМОРФИЗМ")
    for user in (student, teacher):
        print(user)
    print("\nСОЗДАНИЕ ЗАПИСИ")
    booking = create_booking(bookings, student, consultation, 45, now)
    print(booking.confirmation())
    print(f"Слот свободен: {is_available(consultation, bookings)}")
    try:
        create_booking(bookings, student, consultation, 45, now)
    except ValueError as error:
        print(f"Повторная запись отклонена: {error}")
    print("\nОТМЕНА И ПОВТОРНАЯ ЗАПИСЬ")
    booking.cancel()
    print(f"Статус первой записи: {booking.status}")
    print(f"Слот свободен: {is_available(consultation, bookings)}")
    new_booking = create_booking(bookings, student, consultation, 30, now)
    print(new_booking)
    print("\nСОХРАНЕНИЕ И ЗАГРУЗКА JSON")
    with TemporaryDirectory() as directory:
        path = Path(directory) / "consultations.json"
        save_data(path, ([student, teacher], [consultation], bookings))
        users, consultations, restored = load_data(path)
    print(
        f"Загружено: пользователей {len(users)}, консультаций {len(consultations)}, "
        f"записей {len(restored)}"
    )
    print(f"Связь со студентом восстановлена: {restored[1].student is users[0]}")
    print(
        f"Связь с консультацией восстановлена: "
        f"{restored[1].consultation is consultations[0]}"
    )
    print(f"Сохранённая отмена: {restored[0].status}")


if __name__ == "__main__":
    main()
