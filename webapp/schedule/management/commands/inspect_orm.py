"""Read-only ORM examples and a measured N+1 comparison for PR9/10."""

from django.core.management.base import BaseCommand
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from schedule.models import Booking, Consultation, User


class Command(BaseCommand):
    help = "Execute 18 read-only ORM examples and compare related-object query counts."

    def handle(self, *args, **options):
        today = timezone.localdate()
        samples = [
            ("01 all consultations", lambda: list(Consultation.objects.all()[:10])),
            (
                "02 one object",
                lambda: Consultation.objects.get(
                    pk=Consultation.objects.values_list("pk", flat=True).first()
                ),
            ),
            (
                "03 teachers",
                lambda: list(
                    User.objects.filter(role=User.Role.TEACHER).values("username")[:10]
                ),
            ),
            (
                "04 active future",
                lambda: list(
                    Booking.objects.active()
                    .filter(consultation__starts_at__gt=timezone.now())
                    .values("pk")[:10]
                ),
            ),
            (
                "05 related teacher",
                lambda: list(
                    Booking.objects.filter(
                        consultation__teacher__role=User.Role.TEACHER
                    ).values("pk")[:10]
                ),
            ),
            (
                "06 exclude cancelled",
                lambda: list(
                    Booking.objects.exclude(status=Booking.Status.CANCELLED).values(
                        "pk"
                    )[:10]
                ),
            ),
            (
                "07 topic search",
                lambda: list(
                    Consultation.objects.filter(topic__icontains="Django").values(
                        "topic"
                    )[:10]
                ),
            ),
            (
                "08 combined search Q",
                lambda: list(
                    Consultation.objects.filter(
                        Q(topic__icontains="ORM")
                        | Q(teacher__first_name__icontains="Анна")
                    ).values("topic")[:10]
                ),
            ),
            (
                "09 chronological",
                lambda: list(
                    Consultation.objects.order_by("starts_at").values("pk")[:10]
                ),
            ),
            (
                "10 related ordering",
                lambda: list(
                    Booking.objects.order_by(
                        "consultation__teacher__username", "-created_at"
                    ).values("pk")[:10]
                ),
            ),
            (
                "11 select_related",
                lambda: [
                    (b.pk, b.student.username, b.consultation.teacher.username)
                    for b in Booking.objects.with_details()[:10]
                ],
            ),
            (
                "12 reverse relation counts",
                lambda: list(
                    User.objects.filter(role=User.Role.TEACHER)
                    .annotate(slots_count=Count("slots"))
                    .values("username", "slots_count")[:10]
                ),
            ),
            (
                "13 aggregate",
                lambda: Booking.objects.aggregate(
                    total=Count("pk"), minutes=Sum("duration_minutes", default=0)
                ),
            ),
            (
                "14 grouped statuses",
                lambda: list(
                    Booking.objects.order_by()
                    .values("status")
                    .annotate(total=Count("pk"))
                    .order_by("status")
                ),
            ),
            (
                "15 pagination",
                lambda: [
                    b.pk for b in Paginator(Booking.objects.all(), 10).get_page(1)
                ],
            ),
            (
                "16 available slots Exists",
                lambda: list(
                    Consultation.objects.filter(starts_at__gt=timezone.now())
                    .annotate(
                        occupied=Exists(
                            Booking.objects.active().filter(
                                consultation_id=OuterRef("pk")
                            )
                        )
                    )
                    .filter(occupied=False)
                    .values("pk")[:10]
                ),
            ),
            (
                "17 on_date manager",
                lambda: list(Booking.objects.on_date(today).values("pk")[:10]),
            ),
            (
                "18 values_list",
                lambda: list(
                    Consultation.objects.values_list("topic", "teacher__username")[:10]
                ),
            ),
        ]
        for label, execute in samples:
            with CaptureQueriesContext(connection) as queries:
                try:
                    result = execute()
                except Consultation.DoesNotExist:
                    result = "No consultation yet (handled DoesNotExist)."
            self.stdout.write(f"{label}: {result}; SQL queries={len(queries)}")
            for query in queries:
                self.stdout.write(query["sql"])
        for optimized in (False, True):
            queryset = (
                Booking.objects.with_details() if optimized else Booking.objects.all()
            )
            with CaptureQueriesContext(connection) as queries:
                rows = [
                    (b.student.username, b.consultation.teacher.username)
                    for b in queryset[:10]
                ]
            self.stdout.write(
                f"N+1 optimized={optimized}: rows={len(rows)}, "
                f"SQL queries={len(queries)}"
            )
