import json
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .api import schedule_data
from .models import Booking, Consultation, User
from .services import RuleError, cancel_booking, reserve


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class BookingFixture(TestCase):
    def setUp(self):
        cache.clear()
        self.student = User.objects.create_user(
            username="student", password="test-password-long"
        )
        self.other = User.objects.create_user(
            username="other", password="test-password-long"
        )
        self.teacher = User.objects.create_user(
            username="teacher", role="teacher", password="test-password-long"
        )
        self.when = timezone.now() + timedelta(days=2)
        self.slot = Consultation.objects.create(
            teacher=self.teacher, topic="Django", starts_at=self.when
        )


class BookingRulesTests(BookingFixture):
    def test_create_and_end_time(self):
        booking = reserve(self.student, self.slot.pk, 45)
        self.assertEqual(booking.ends_at, self.when + timedelta(minutes=45))

    def test_duration_boundaries_and_types(self):
        for value in (14, 91, True, 45.5, "45", None):
            with self.subTest(value=value), self.assertRaises(RuleError):
                reserve(self.student, self.slot.pk, value)
        for value in (15, 90):
            booking = reserve(self.student, self.slot.pk, value)
            cancel_booking(self.student, booking.pk)

    def test_past_slot_rejected(self):
        self.slot.starts_at = timezone.now() - timedelta(minutes=1)
        self.slot.save()
        with self.assertRaises(RuleError):
            reserve(self.student, self.slot.pk, 30)

    def test_teacher_cannot_book(self):
        with self.assertRaises(RuleError) as ctx:
            reserve(self.teacher, self.slot.pk, 30)
        self.assertEqual(ctx.exception.status, 403)

    def test_same_slot_rejected_for_another_student(self):
        reserve(self.student, self.slot.pk, 45)
        with self.assertRaises(RuleError):
            reserve(self.other, self.slot.pk, 45)

    def test_teacher_overlap_rejected(self):
        reserve(self.student, self.slot.pk, 45)
        second = Consultation.objects.create(
            teacher=self.teacher,
            topic="SQL",
            starts_at=self.when + timedelta(minutes=15),
        )
        with self.assertRaises(RuleError):
            reserve(self.other, second.pk, 30)

    def test_student_overlap_with_another_teacher(self):
        reserve(self.student, self.slot.pk, 45)
        other_teacher = User.objects.create_user(username="teacher2", role="teacher")
        second = Consultation.objects.create(
            teacher=other_teacher,
            topic="SQL",
            starts_at=self.when + timedelta(minutes=15),
        )
        with self.assertRaises(RuleError):
            reserve(self.student, second.pk, 30)

    def test_adjacent_meetings_allowed(self):
        reserve(self.student, self.slot.pk, 45)
        second = Consultation.objects.create(
            teacher=self.teacher,
            topic="SQL",
            starts_at=self.when + timedelta(minutes=45),
        )
        reserve(self.student, second.pk, 30)
        self.assertEqual(Booking.objects.count(), 2)

    def test_cancel_is_idempotent_and_releases_slot(self):
        booking = reserve(self.student, self.slot.pk, 30)
        cancel_booking(self.student, booking.pk)
        cancel_booking(self.student, booking.pk)
        reserve(self.other, self.slot.pk, 30)
        self.assertEqual(Booking.objects.active().count(), 1)

    def test_cancel_another_students_booking_rejected(self):
        booking = reserve(self.student, self.slot.pk, 30)
        with self.assertRaises(RuleError):
            cancel_booking(self.other, booking.pk)

    def test_teacher_can_cancel_own_consultation_booking(self):
        booking = reserve(self.student, self.slot.pk, 30)
        self.assertTrue(cancel_booking(self.teacher, booking.pk).is_cancelled)

    def test_database_guards_slot_uniqueness(self):
        reserve(self.student, self.slot.pk, 30)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Booking.objects.create(
                student=self.other,
                consultation=self.slot,
                duration_minutes=30,
                ends_at=self.when + timedelta(minutes=30),
            )

    def test_cache_reduces_schedule_queries(self):
        with self.assertNumQueries(1):
            cold, hit = schedule_data()
        self.assertFalse(hit)
        with self.assertNumQueries(0):
            warm, hit = schedule_data()
        self.assertTrue(hit)
        self.assertEqual(cold, warm)

    def test_booking_invalidates_cached_availability(self):
        schedule_data()
        with self.captureOnCommitCallbacks(execute=True):
            reserve(self.student, self.slot.pk, 30)
        result, hit = schedule_data()
        self.assertFalse(hit)
        self.assertFalse(result[0]["available"])

    def test_cancel_invalidates_cached_availability(self):
        booking = reserve(self.student, self.slot.pk, 30)
        schedule_data()
        with self.captureOnCommitCallbacks(execute=True):
            cancel_booking(self.student, booking.pk)
        self.assertTrue(schedule_data()[0][0]["available"])


class ApiTests(BookingFixture):
    def post(self, path, data, client=None):
        return (client or self.client).post(
            path, json.dumps(data), content_type="application/json"
        )

    def test_full_api_booking_lifecycle(self):
        self.client.force_login(self.student)
        response = self.post(
            "/api/bookings/", {"consultation_id": self.slot.pk, "duration_minutes": 45}
        )
        self.assertEqual(response.status_code, 201)
        booking_id = response.json()["id"]
        self.assertEqual(len(self.client.get("/api/bookings/").json()["results"]), 1)
        self.assertEqual(
            self.post(f"/api/bookings/{booking_id}/cancel/", {}).status_code, 200
        )

    def test_anonymous_cannot_read_private_bookings(self):
        self.assertEqual(self.client.get("/api/bookings/").status_code, 401)

    def test_no_leak_between_students(self):
        reserve(self.student, self.slot.pk, 30)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get("/api/bookings/").json()["results"], [])

    def test_server_template_status_changes_and_privacy(self):
        booking = reserve(self.student, self.slot.pk, 30)
        self.client.force_login(self.student)
        self.assertContains(self.client.get(f"/bookings/{booking.pk}/"), "Подтверждена")
        cancel_booking(self.student, booking.pk)
        self.assertContains(self.client.get(f"/bookings/{booking.pk}/"), "Отменена")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f"/bookings/{booking.pk}/").status_code, 403)

    def test_student_cannot_create_slot(self):
        self.client.force_login(self.student)
        self.assertEqual(self.post("/api/consultations/", {}).status_code, 403)

    def test_teacher_creates_only_own_slot(self):
        self.client.force_login(self.teacher)
        response = self.post(
            "/api/consultations/",
            {
                "topic": "API",
                "location": "Онлайн",
                "starts_at": (self.when + timedelta(days=1)).isoformat(),
                "teacher_id": self.other.pk,
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Consultation.objects.get(pk=response.json()["id"]).teacher, self.teacher
        )

    def test_invalid_and_naive_date(self):
        self.client.force_login(self.teacher)
        for value in ("tomorrow", "2026-02-30T10:00:00+03:00", "2026-11-01T10:00", 10):
            self.assertEqual(
                self.post(
                    "/api/consultations/",
                    {"topic": "API", "location": "Online", "starts_at": value},
                ).status_code,
                400,
            )

    def test_invalid_json_returns_400(self):
        self.assertEqual(
            self.client.post(
                "/api/auth/login/", "{", content_type="application/json"
            ).status_code,
            400,
        )

    def test_wrong_content_type_returns_415(self):
        self.assertEqual(
            self.client.post("/api/auth/login/", {"username": "abc"}).status_code, 415
        )

    def test_signup_cannot_promote_self(self):
        response = self.post(
            "/api/auth/register/",
            {
                "username": "new_student",
                "name": "Новый студент",
                "password": "Safe-study-password-827!",
                "role": "teacher",
                "is_staff": True,
            },
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="new_student")
        self.assertEqual(user.role, "student")
        self.assertFalse(user.is_staff)
        self.assertNotEqual(user.password, "Safe-study-password-827!")

    def test_weak_password_rejected(self):
        self.assertEqual(
            self.post(
                "/api/auth/register/",
                {"username": "new_student", "name": "Test", "password": "123"},
            ).status_code,
            400,
        )

    def test_login_invalid_and_logout(self):
        self.assertEqual(
            self.post(
                "/api/auth/login/", {"username": "student", "password": "bad"}
            ).status_code,
            401,
        )
        self.assertEqual(
            self.post(
                "/api/auth/login/",
                {"username": "student", "password": "test-password-long"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get("/api/auth/me/").json()["user"]["role"], "student"
        )
        self.post("/api/auth/logout/", {})
        self.assertIsNone(self.client.get("/api/auth/me/").json()["user"])

    def test_login_rate_limit(self):
        for _ in range(10):
            self.post("/api/auth/login/", {"username": "student", "password": "bad"})
        self.assertEqual(
            self.post(
                "/api/auth/login/", {"username": "student", "password": "bad"}
            ).status_code,
            429,
        )

    def test_csrf_is_required_for_login(self):
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(
            self.post(
                "/api/auth/login/",
                {"username": "student", "password": "test-password-long"},
                strict,
            ).status_code,
            403,
        )
        token = strict.get("/api/csrf/").json()["csrfToken"]
        response = strict.post(
            "/api/auth/login/",
            json.dumps({"username": "student", "password": "test-password-long"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.cookies["sessionid"]["httponly"])

    def test_csrf_is_required_after_login(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.student)
        self.assertEqual(
            self.post(
                "/api/bookings/",
                {"consultation_id": self.slot.pk, "duration_minutes": 30},
                strict,
            ).status_code,
            403,
        )

    def test_security_headers_and_methods(self):
        response = self.client.get("/api/consultations/")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertIn("default-src 'self'", response["Content-Security-Policy"])
        self.assertEqual(self.client.get("/api/auth/logout/").status_code, 405)

    def test_search_cyrillic_and_injection_literal(self):
        self.slot.topic = "Базы данных"
        self.slot.save()
        self.assertEqual(
            self.client.get("/api/consultations/?q=БАЗЫ").json()["count"], 1
        )
        self.assertEqual(
            self.client.get("/api/consultations/", {"q": "' OR 1=1 --"}).json()[
                "count"
            ],
            0,
        )

    def test_health_and_failed_cache(self):
        self.assertEqual(self.client.get("/health/ready/").status_code, 200)
        with patch("schedule.api.cache.set", side_effect=ConnectionError):
            self.assertEqual(self.client.get("/health/ready/").status_code, 503)

    @override_settings(ALLOWED_HOSTS=["localhost"])
    def test_unknown_host_rejected(self):
        self.assertEqual(
            self.client.get("/", HTTP_HOST="untrusted.example").status_code, 400
        )
