"""Business rules and database locking for simultaneous bookings."""

from datetime import timedelta

from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Booking, Consultation, User


class RuleError(Exception):
    def __init__(self, message, status=400):
        self.status = status
        super().__init__(message)


def invalidate_schedule():
    cache.delete("schedule:upcoming")


@transaction.atomic
def reserve(student, consultation_id, duration):
    if student.role != User.Role.STUDENT:
        raise RuleError("Записываться может только студент.", 403)
    if type(duration) is not int or not 15 <= duration <= 90:
        raise RuleError("Длительность — целое число от 15 до 90 минут.")
    try:
        slot = Consultation.objects.get(pk=consultation_id)
    except Consultation.DoesNotExist:
        raise RuleError("Консультация не найдена.", 404)
    # Lock shared participants in one order before reading active bookings.
    # PostgreSQL serializes reservations for a teacher or student across slots.
    list(
        User.objects.select_for_update()
        .filter(pk__in=[student.pk, slot.teacher_id])
        .order_by("pk")
    )
    end = validate_reservation(student, slot, duration)
    booking = Booking.objects.create(
        student=student, consultation=slot, duration_minutes=duration, ends_at=end
    )
    transaction.on_commit(invalidate_schedule)
    return booking


def validate_reservation(student, slot, duration, exclude_pk=None):
    if student.role != User.Role.STUDENT:
        raise RuleError("Записываться может только студент.", 403)
    if type(duration) is not int or not 15 <= duration <= 90:
        raise RuleError("Длительность — целое число от 15 до 90 минут.")
    if slot.teacher.role != User.Role.TEACHER:
        raise RuleError("Консультацию должен проводить преподаватель.")
    if slot.starts_at <= timezone.now():
        raise RuleError("Консультация уже началась или прошла.", 409)
    end = slot.starts_at + timedelta(minutes=duration)
    active = Booking.objects.active().exclude(pk=exclude_pk)
    if active.filter(consultation=slot).exists():
        raise RuleError("Это время уже занято. Выберите другую консультацию.", 409)
    if active.filter(
        Q(student=student) | Q(consultation__teacher_id=slot.teacher_id),
        consultation__starts_at__lt=end,
        ends_at__gt=slot.starts_at,
    ).exists():
        raise RuleError(
            "У студента или преподавателя уже есть встреча в это время.", 409
        )
    return end


@transaction.atomic
def save_booking_form(form, student):
    """Recheck availability under the same participant locks as the API."""
    slot = form.cleaned_data["consultation"]
    duration = form.cleaned_data["duration_minutes"]
    existing = None
    if form.instance.pk:
        existing = Booking.objects.select_for_update().get(pk=form.instance.pk)
        if existing.student_id != student.pk:
            raise RuleError("Нельзя редактировать чужую запись.", 403)
        if existing.status != Booking.Status.ACTIVE:
            raise RuleError("Редактировать можно только активную запись.", 409)
        if existing.consultation.starts_at <= timezone.now():
            raise RuleError("Начавшуюся встречу нельзя переносить.", 409)
    participant_ids = [student.pk, slot.teacher_id]
    if existing:
        participant_ids.append(existing.consultation.teacher_id)
    list(User.objects.select_for_update().filter(pk__in=participant_ids).order_by("pk"))
    end = validate_reservation(student, slot, duration, form.instance.pk)
    booking = form.save(commit=False)
    booking.student = student
    booking.status = Booking.Status.ACTIVE
    booking.ends_at = end
    booking.save()
    transaction.on_commit(invalidate_schedule)
    return booking


@transaction.atomic
def cancel_booking(user, booking_id):
    try:
        booking = Booking.objects.select_for_update().get(pk=booking_id)
    except Booking.DoesNotExist:
        raise RuleError("Запись не найдена.", 404)
    if user.pk not in (booking.student_id, booking.consultation.teacher_id):
        raise RuleError("Нельзя отменить чужую запись.", 403)
    list(
        User.objects.select_for_update()
        .filter(pk__in=[booking.student_id, booking.consultation.teacher_id])
        .order_by("pk")
    )
    booking.refresh_from_db()
    if booking.status == Booking.Status.COMPLETED:
        raise RuleError("Завершённую встречу нельзя отменить.", 409)
    if not booking.is_cancelled:
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status"])
        transaction.on_commit(invalidate_schedule)
    return booking
