from datetime import timedelta

from django.contrib import admin
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TransactionTestCase
from django.utils import timezone

from .admin import ConsultationAdminForm
from .forms import BookingForm
from .models import Booking, Consultation
from .services import RuleError, cancel_booking, reserve, save_booking_form
from .tests import BookingFixture


class FormsTests(BookingFixture):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.student)

    def test_create_edit_cancel_and_rebook(self):
        response = self.client.post(
            "/bookings/new/", {"consultation": self.slot.pk, "duration_minutes": 30}
        )
        booking = Booking.objects.get()
        self.assertRedirects(response, booking.get_absolute_url())
        response = self.client.post(
            f"/bookings/{booking.pk}/edit/",
            {"consultation": self.slot.pk, "duration_minutes": 45},
        )
        self.assertRedirects(response, booking.get_absolute_url())
        booking.refresh_from_db()
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(booking.ends_at, self.when + timedelta(minutes=45))
        self.assertEqual(
            self.client.get(f"/bookings/{booking.pk}/cancel/").status_code, 405
        )
        self.client.post(f"/bookings/{booking.pk}/cancel/")
        self.assertTrue(Booking.objects.get().is_cancelled)
        self.assertEqual(
            reserve(self.other, self.slot.pk, 30).status, Booking.Status.ACTIVE
        )

    def test_invalid_duration_and_missing_consultation_keep_values(self):
        response = self.client.post(
            "/bookings/new/", {"consultation": self.slot.pk, "duration_minutes": 14}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("duration_minutes", response.context["form"].errors)
        self.assertEqual(response.context["form"]["duration_minutes"].value(), "14")
        self.assertFalse(Booking.objects.exists())
        response = self.client.post(
            "/bookings/new/", {"consultation": 99999, "duration_minutes": 30}
        )
        self.assertIn("consultation", response.context["form"].errors)

    def test_student_identity_and_status_cannot_be_forged(self):
        self.client.post(
            "/bookings/new/",
            {
                "consultation": self.slot.pk,
                "duration_minutes": 30,
                "student": self.other.pk,
                "status": "completed",
            },
        )
        booking = Booking.objects.get()
        self.assertEqual(booking.student, self.student)
        self.assertEqual(booking.status, Booking.Status.ACTIVE)

    def test_conflict_on_edit_preserves_original(self):
        original = reserve(self.student, self.slot.pk, 30)
        second = Consultation.objects.create(
            teacher=self.teacher, starts_at=self.when + timedelta(hours=2), topic="SQL"
        )
        reserve(self.other, second.pk, 30)
        response = self.client.post(
            f"/bookings/{original.pk}/edit/",
            {"consultation": second.pk, "duration_minutes": 30},
        )
        self.assertTrue(response.context["form"].non_field_errors())
        original.refresh_from_db()
        self.assertEqual(original.consultation, self.slot)

    def test_conflict_created_after_form_validation(self):
        form = BookingForm(
            {"consultation": self.slot.pk, "duration_minutes": 30}, student=self.student
        )
        self.assertTrue(form.is_valid())
        reserve(self.other, self.slot.pk, 30)
        with self.assertRaises(RuleError):
            save_booking_form(form, self.student)
        self.assertEqual(Booking.objects.count(), 1)

    def test_cancelled_record_cannot_be_reactivated_by_stale_form(self):
        booking = reserve(self.student, self.slot.pk, 30)
        form = BookingForm(
            {"consultation": self.slot.pk, "duration_minutes": 30},
            student=self.student,
            instance=booking,
        )
        self.assertTrue(form.is_valid())
        cancel_booking(self.student, booking.pk)
        with self.assertRaises(RuleError):
            save_booking_form(form, self.student)

    def test_foreign_and_missing_objects(self):
        booking = reserve(self.other, self.slot.pk, 30)
        for path in (
            f"/bookings/{booking.pk}/edit/",
            f"/bookings/{booking.pk}/cancel/",
        ):
            self.assertEqual(self.client.post(path).status_code, 403)
        self.assertEqual(self.client.get("/bookings/99999/edit/").status_code, 404)
        self.assertEqual(self.client.post("/bookings/99999/cancel/").status_code, 404)

    def test_csrf_on_all_html_mutations(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.student)
        booking = reserve(self.student, self.slot.pk, 30)
        for path in (
            "/bookings/new/",
            f"/bookings/{booking.pk}/edit/",
            f"/bookings/{booking.pk}/cancel/",
        ):
            self.assertEqual(strict.post(path, {}).status_code, 403)

    def test_anonymous_redirect_and_teacher_cannot_create(self):
        self.client.logout()
        self.assertEqual(self.client.get("/bookings/").status_code, 302)
        self.assertContains(self.client.get("/accounts/login/"), "csrfmiddlewaretoken")
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get("/bookings/new/").status_code, 403)

    def test_filter_validation_and_pagination(self):
        for i in range(12):
            slot = Consultation.objects.create(
                teacher=self.teacher,
                topic="Django page",
                starts_at=self.when + timedelta(hours=i + 1),
            )
            reserve(self.student, slot.pk, 30)
        reserve(self.other, self.slot.pk, 30)
        response = self.client.get(
            "/bookings/", {"q": "Django", "status": "active", "sort": "-date"}
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 12)
        self.assertEqual(len(response.context["page_obj"]), 10)
        self.assertContains(
            response, "q=Django&amp;status=active&amp;sort=-date&amp;page=2"
        )
        self.assertEqual(
            len(self.client.get("/bookings/?page=2").context["page_obj"]), 2
        )
        for query in (
            "date_from=bad",
            "teacher=99999",
            "sort=DROP",
            "status=wrong",
            "date_from=2026-12-31&date_to=2026-01-01",
        ):
            response = self.client.get("/bookings/?" + query)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
            self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_statistics_private_and_completed_status(self):
        booking = reserve(self.student, self.slot.pk, 30)
        Booking.objects.filter(pk=booking.pk).update(status=Booking.Status.COMPLETED)
        response = self.client.get("/statistics/")
        self.assertEqual(response.context["totals"]["completed"], 1)
        self.assertEqual(
            self.client.get("/api/bookings/").json()["results"][0]["status"],
            "completed",
        )
        with self.assertRaises(RuleError):
            cancel_booking(self.student, booking.pk)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get("/statistics/").context["totals"]["total"], 0)

    def test_slug_and_admin_pages(self):
        self.assertContains(self.client.get(self.slot.get_absolute_url()), "Django")
        self.student.is_staff = self.student.is_superuser = True
        self.student.save()
        reserve(self.student, self.slot.pk, 30)
        for path in (
            "/admin/schedule/consultation/",
            "/admin/schedule/booking/",
            f"/admin/schedule/consultation/{self.slot.pk}/change/",
        ):
            self.assertEqual(self.client.get(path).status_code, 200)
        self.assertIn(Booking, admin.site._registry)

    def test_admin_cannot_move_consultation_with_bookings(self):
        reserve(self.student, self.slot.pk, 30)
        form = ConsultationAdminForm(
            {
                "teacher": self.teacher.pk,
                "topic": "Django",
                "starts_at": self.when + timedelta(hours=1),
                "location": "Online",
            },
            instance=self.slot,
        )
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())


class MigrationPreservationTests(TransactionTestCase):
    def test_cancelled_flags_ids_and_relations_survive(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes("schedule")
        try:
            executor.migrate([("schedule", "0001_initial")])
            old = executor.loader.project_state([("schedule", "0001_initial")]).apps
            User = old.get_model("schedule", "User")
            Slot = old.get_model("schedule", "Consultation")
            OldBooking = old.get_model("schedule", "Booking")
            teacher = User.objects.create(username="migration-teacher", role="teacher")
            student = User.objects.create(username="migration-student")
            slot = Slot.objects.create(
                teacher=teacher, topic="Migration", starts_at=timezone.now()
            )
            cancelled = OldBooking.objects.create(
                student=student,
                consultation=slot,
                duration_minutes=30,
                ends_at=timezone.now(),
                is_cancelled=True,
            )
            active = OldBooking.objects.create(
                student=student,
                consultation=slot,
                duration_minutes=30,
                ends_at=timezone.now(),
                is_cancelled=False,
            )
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            self.assertEqual(Booking.objects.get(pk=cancelled.pk).status, "cancelled")
            self.assertEqual(Booking.objects.get(pk=active.pk).status, "active")
            self.assertEqual(Booking.objects.get(pk=active.pk).student_id, student.pk)
            self.assertEqual(
                Consultation.objects.get(pk=slot.pk).slug, f"consultation-{slot.pk}"
            )
        finally:
            MigrationExecutor(connection).migrate(latest)
