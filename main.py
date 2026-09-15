"""ПР1: запись одного студента на консультацию преподавателя."""

from datetime import datetime, timedelta


def get_booking_status(is_available, starts_at, current_time, duration_minutes):
    """Проверить свободный слот, дату и длительность консультации."""
    if not is_available:
        return "Отказ: выбранное время уже занято."
    elif starts_at <= current_time:
        return "Отказ: консультация уже началась или прошла."
    elif duration_minutes < 15 or duration_minutes > 90:
        return "Отказ: длительность должна быть от 15 до 90 минут."
    return "Запись доступна."


def calculate_end_time(starts_at, duration_minutes):
    """Рассчитать окончание консультации по началу и длительности."""
    ends_at = starts_at + timedelta(minutes=duration_minutes)
    return ends_at


def create_confirmation(student_name, teacher_name, topic, starts_at, ends_at):
    """Сформировать подтверждение записи с датой и временем."""
    return (
        f"Запись подтверждена!\n"
        f"Студент: {student_name}\n"
        f"Преподаватель: {teacher_name}\n"
        f"Тема: {topic}\n"
        f"Начало: {starts_at:%d.%m.%Y %H:%M}\n"
        f"Окончание: {ends_at:%d.%m.%Y %H:%M}"
    )


def main():
    """Выполнить один законченный сценарий записи в консоли."""
    teacher_name = "Иванова Анна Сергеевна"
    topic = "Основы Python"
    current_time = datetime.now()
    starts_at = (current_time + timedelta(days=1)).replace(
        hour=15, minute=0, second=0, microsecond=0
    )
    is_available = True

    print("Система управления консультациями")
    print(f"Преподаватель: {teacher_name}")
    print(f"Тема: {topic}")
    print(f"Доступное время: {starts_at:%d.%m.%Y %H:%M}")

    student_name = input("Введите имя студента: ").strip()
    if not student_name:
        print("Отказ: имя студента не должно быть пустым.")
        return

    duration_text = input("Длительность консультации (15–90 минут): ").strip()
    if not duration_text.isdecimal() or len(duration_text) > 3:
        print("Отказ: введите целое число минут от 15 до 90.")
        return

    duration_minutes = int(duration_text)
    duration_hours = duration_minutes / 60
    status = get_booking_status(
        is_available, starts_at, datetime.now(), duration_minutes
    )
    print(status)
    if status != "Запись доступна.":
        return

    ends_at = calculate_end_time(starts_at, duration_minutes)
    is_available = False
    print(create_confirmation(
        student_name, teacher_name, topic, starts_at, ends_at
    ))
    print(f"Длительность: {duration_minutes} мин. ({duration_hours:.2f} ч.)")
    print(f"Слот свободен: {is_available}")
    print("Учебный режим: запись хранится только до завершения программы.")


if __name__ == "__main__":
    main()
