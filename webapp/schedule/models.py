from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .querysets import BookingQuerySet


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "Студент"
        TEACHER = "teacher", "Преподаватель"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    def __str__(self):
        return self.display_name


class Consultation(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.PROTECT, related_name="slots")
    topic = models.CharField(max_length=160)
    starts_at = models.DateTimeField(db_index=True)
    location = models.CharField(max_length=120, default="Онлайн")
    slug = models.SlugField(max_length=180, unique=True, blank=True)

    def __str__(self):
        return f"{self.topic} — {timezone.localtime(self.starts_at):%d.%m.%Y %H:%M}"

    def save(self, *args, **kwargs):
        if not self.slug:
            from uuid import uuid4
            from django.utils.text import slugify

            self.slug = f"{slugify(self.topic)[:130] or 'consultation'}-{uuid4().hex}"
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("consultation_detail", kwargs={"slug": self.slug})

    class Meta:
        verbose_name = "консультация"
        verbose_name_plural = "консультации"
        ordering = ["starts_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["teacher", "starts_at"], name="unique_teacher_start"
            )
        ]


class Booking(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Подтверждена"
        CANCELLED = "cancelled", "Отменена"
        COMPLETED = "completed", "Завершена"

    objects = BookingQuerySet.as_manager()
    student = models.ForeignKey(User, on_delete=models.PROTECT, related_name="bookings")
    consultation = models.ForeignKey(
        Consultation, on_delete=models.PROTECT, related_name="bookings"
    )
    duration_minutes = models.PositiveSmallIntegerField()
    ends_at = models.DateTimeField()
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_cancelled(self):
        """Compatibility for existing templates and the JSON API."""
        return self.status == self.Status.CANCELLED

    def __str__(self):
        return f"Запись №{self.pk}: {self.student} — {self.consultation}"

    def get_absolute_url(self):
        return reverse("booking_detail", kwargs={"booking_id": self.pk})

    def cancel(self, user):
        from .services import cancel_booking

        return cancel_booking(user, self.pk)

    class Meta:
        verbose_name = "запись"
        verbose_name_plural = "записи"
        ordering = ["consultation__starts_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["consultation"],
                condition=Q(status="active"),
                name="one_active_booking_per_slot",
            ),
            models.CheckConstraint(
                condition=Q(duration_minutes__gte=15, duration_minutes__lte=90),
                name="duration_15_to_90",
            ),
        ]
        indexes = [
            models.Index(
                fields=["student", "status"], name="booking_student_status_idx"
            )
        ]
