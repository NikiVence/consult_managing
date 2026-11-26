import hashlib
import json
import re
from functools import wraps
from pathlib import Path

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models import Exists, OuterRef
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import ensure_csrf_cookie

from .models import Booking, Consultation, User
from .services import RuleError, cancel_booking, invalidate_schedule, reserve


def error(message, status=400):
    return JsonResponse({"error": message}, status=status)


def endpoint(methods, authenticated=False):
    def decorate(fn):
        @wraps(fn)
        def wrapped(request, *args, **kwargs):
            if request.method not in methods:
                response = error("Метод не поддерживается.", 405)
                response["Allow"] = ", ".join(methods)
                return response
            if authenticated and not request.user.is_authenticated:
                return error("Войдите в аккаунт.", 401)
            try:
                return fn(request, *args, **kwargs)
            except RuleError as exc:
                return error(str(exc), exc.status)
            except ValidationError as exc:
                return error(" ".join(exc.messages))
            except IntegrityError:
                return error("Такая запись уже существует. Обновите страницу.", 409)
            except DatabaseError:
                return error("База данных временно недоступна. Повторите запрос.", 503)

        return wrapped

    return decorate


def payload(request):
    if request.content_type != "application/json":
        raise RuleError("Используйте Content-Type: application/json.", 415)
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeError):
        raise RuleError("Некорректный JSON.")
    if not isinstance(data, dict):
        raise RuleError("Ожидается JSON-объект.")
    return data


def text_field(data, name, maximum, minimum=1):
    value = data.get(name)
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise RuleError(f"Поле {name}: от {minimum} до {maximum} символов.")
    return value.strip()


def user_data(user):
    return {
        "id": user.pk,
        "username": user.username,
        "name": user.display_name,
        "role": user.role,
    }


def throttle(request, namespace, limit=10):
    # Uses the socket peer, never an untrusted X-Forwarded-For header.
    peer = request.META.get("REMOTE_ADDR", "unknown")
    digest = hashlib.sha256(peer.encode()).hexdigest()
    key = f"limit:{namespace}:{digest}"
    if cache.add(key, 1, timeout=60):
        return
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=60)
        count = 1
    if count > limit:
        raise RuleError("Слишком много попыток. Подождите минуту.", 429)


@ensure_csrf_cookie
def home(request):
    return render(request, "index.html")


def docs(request):
    return render(request, "api_docs.html")


def openapi(request):
    schema = Path(__file__).resolve().parent.parent / "openapi.json"
    return JsonResponse(json.loads(schema.read_text(encoding="utf-8")))


@endpoint(["GET"])
def csrf_token(request):
    return JsonResponse({"csrfToken": get_token(request)})


def csrf_failure(request, reason=""):
    return error("CSRF-проверка не пройдена. Обновите страницу.", 403)


@endpoint(["POST"])
def register(request):
    throttle(request, "register", 5)
    data = payload(request)
    username = text_field(data, "username", 40, 3)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        raise RuleError(
            "Логин: латинские буквы, цифры, точка, дефис или подчёркивание."
        )
    name = text_field(data, "name", 150, 2)
    password = data.get("password")
    if not isinstance(password, str) or len(password) > 128:
        raise RuleError("Укажите пароль до 128 символов.")
    user = User(username=username, first_name=name)
    validate_password(password, user)
    user.set_password(password)
    with transaction.atomic():
        user.save()
    login(request, user)
    return JsonResponse({"user": user_data(user)}, status=201)


@endpoint(["POST"])
def sign_in(request):
    throttle(request, "login")
    data = payload(request)
    username = text_field(data, "username", 150)
    password = data.get("password")
    if not isinstance(password, str) or len(password) > 128:
        raise RuleError("Некорректный пароль.")
    user = authenticate(request, username=username, password=password)
    if user is None:
        raise RuleError("Неверный логин или пароль.", 401)
    login(request, user)
    return JsonResponse({"user": user_data(user)})


@endpoint(["POST"], authenticated=True)
def sign_out(request):
    logout(request)
    return JsonResponse({"ok": True})


@endpoint(["GET"])
def me(request):
    return JsonResponse(
        {"user": user_data(request.user) if request.user.is_authenticated else None}
    )


def schedule_data():
    result = cache.get("schedule:upcoming")
    hit = result is not None
    if result is None:
        slots = (
            Consultation.objects.filter(starts_at__gt=timezone.now())
            .select_related("teacher")
            .annotate(
                occupied=Exists(
                    Booking.objects.filter(
                        consultation=OuterRef("pk"), status=Booking.Status.ACTIVE
                    )
                )
            )[:200]
        )
        result = [
            {
                "id": slot.pk,
                "topic": slot.topic,
                "teacher": slot.teacher.display_name,
                "teacher_id": slot.teacher_id,
                "starts_at": slot.starts_at.isoformat(),
                "location": slot.location,
                "available": not slot.occupied,
            }
            for slot in slots
        ]
        cache.set("schedule:upcoming", result, timeout=15)
    # A cached slot must not remain visible after its start time.
    now = timezone.now()
    return [slot for slot in result if parse_datetime(slot["starts_at"]) > now], hit


@endpoint(["GET", "POST"])
def consultations(request):
    if request.method == "GET":
        query = request.GET.get("q", "").strip().casefold()[:100]
        result, hit = schedule_data()
        if query:
            result = [
                s
                for s in result
                if query in (s["topic"] + " " + s["teacher"]).casefold()
            ]
        response = JsonResponse({"results": result, "count": len(result)})
        response["X-Cache"] = "HIT" if hit else "MISS"
        return response
    if not request.user.is_authenticated:
        raise RuleError("Войдите в аккаунт.", 401)
    if request.user.role != User.Role.TEACHER:
        raise RuleError("Создавать консультации может только преподаватель.", 403)
    data = payload(request)
    topic = text_field(data, "topic", 160)
    location = text_field(data, "location", 120)
    raw_date = data.get("starts_at", "")
    try:
        starts_at = parse_datetime(raw_date) if isinstance(raw_date, str) else None
    except ValueError:
        starts_at = None
    if starts_at is None or timezone.is_naive(starts_at):
        raise RuleError("Укажите дату и время ISO 8601 с часовым поясом.")
    if starts_at <= timezone.now():
        raise RuleError("Выберите будущее время.")
    with transaction.atomic():
        slot = Consultation.objects.create(
            teacher=request.user, topic=topic, location=location, starts_at=starts_at
        )
        transaction.on_commit(invalidate_schedule)
    return JsonResponse({"id": slot.pk, "topic": slot.topic}, status=201)


def booking_data(booking):
    slot = booking.consultation
    return {
        "id": booking.pk,
        "consultation_id": slot.pk,
        "topic": slot.topic,
        "teacher": slot.teacher.display_name,
        "student": booking.student.display_name,
        "starts_at": slot.starts_at.isoformat(),
        "ends_at": booking.ends_at.isoformat(),
        "duration_minutes": booking.duration_minutes,
        "location": slot.location,
        "status": (
            "confirmed" if booking.status == Booking.Status.ACTIVE else booking.status
        ),
    }


@endpoint(["GET"], authenticated=True)
def booking_detail(request, booking_id):
    try:
        booking = Booking.objects.select_related(
            "student", "consultation__teacher"
        ).get(pk=booking_id)
    except Booking.DoesNotExist:
        raise RuleError("Запись не найдена.", 404)
    if request.user.pk not in (booking.student_id, booking.consultation.teacher_id):
        raise RuleError("Нет доступа к чужой записи.", 403)
    return render(request, "booking_detail.html", {"booking": booking})


@endpoint(["GET", "POST"], authenticated=True)
def bookings(request):
    if request.method == "POST":
        data = payload(request)
        slot_id = data.get("consultation_id")
        if type(slot_id) is not int or slot_id < 1:
            raise RuleError("Некорректный ID консультации.")
        booking = reserve(request.user, slot_id, data.get("duration_minutes"))
        return JsonResponse(booking_data(booking), status=201)
    query = Booking.objects.with_details().for_user(request.user)
    return JsonResponse({"results": [booking_data(b) for b in query[:200]]})


@endpoint(["POST"], authenticated=True)
def cancel(request, booking_id):
    booking = cancel_booking(request.user, booking_id)
    return JsonResponse(booking_data(booking))


@endpoint(["GET"])
def live(request):
    return JsonResponse({"status": "ok", "service": "consultations"})


@endpoint(["GET"])
def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        cache.set("health:probe", "ok", timeout=5)
        if cache.get("health:probe") != "ok":
            raise RuntimeError("Cache check failed")
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ready", "database": "ok", "cache": "ok"})
