import os
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from schedule.models import Consultation, User


class Command(BaseCommand):
    help = (
        "Create demo accounts and future slots; existing passwords/data are preserved."
    )

    def handle(self, *args, **options):
        accounts = [
            ("student", "Никита Алиев", User.Role.STUDENT, "DEMO_STUDENT_PASSWORD"),
            ("teacher", "Анна Иванова", User.Role.TEACHER, "DEMO_TEACHER_PASSWORD"),
        ]
        for username, name, role, variable in accounts:
            if not User.objects.filter(username=username).exists():
                password = os.environ.get(variable)
                if not password:
                    raise CommandError(f"Set {variable} before creating demo accounts.")
                User.objects.create_user(
                    username=username, first_name=name, role=role, password=password
                )
        teacher = User.objects.get(username="teacher")
        tomorrow = timezone.localtime().replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        topics = [
            "Проектирование Django-приложения",
            "Базы данных и ORM",
            "Подготовка к защите проекта",
            "REST API и безопасность",
            "Тестирование веб-приложений",
            "Развёртывание и Docker",
        ]
        for index, topic in enumerate(topics):
            Consultation.objects.get_or_create(
                teacher=teacher,
                starts_at=tomorrow + timedelta(hours=index * 2),
                defaults={
                    "topic": topic,
                    "location": "Аудитория И-312" if index % 2 == 0 else "Онлайн",
                },
            )
        self.stdout.write(
            self.style.SUCCESS("Demo accounts and six future consultations are ready.")
        )
