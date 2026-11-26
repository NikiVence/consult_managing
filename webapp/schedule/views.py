from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .forms import BookingFilterForm, BookingForm
from .models import Booking, Consultation, User
from .services import RuleError, cancel_booking, save_booking_form


class AccountLoginView(LoginView):
    def post(self, request, *args, **kwargs):
        from .api import throttle

        try:
            throttle(request, "login")
        except RuleError as exc:
            form = self.get_form()
            form.is_valid()
            form.add_error(None, str(exc))
            response = self.form_invalid(form)
            response.status_code = 429
            return response
        return super().post(request, *args, **kwargs)


@login_required
def booking_list(request):
    form = BookingFilterForm(request.GET)
    bookings = Booking.objects.for_user(request.user).with_details()
    if form.is_valid():
        data = form.cleaned_data
        if data["date_from"]:
            bookings = bookings.filter(
                consultation__starts_at__date__gte=data["date_from"]
            )
        if data["date_to"]:
            bookings = bookings.filter(
                consultation__starts_at__date__lte=data["date_to"]
            )
        if data["teacher"]:
            bookings = bookings.filter(consultation__teacher=data["teacher"])
        if data["status"]:
            bookings = bookings.filter(status=data["status"])
        if data["q"]:
            bookings = bookings.filter(
                Q(consultation__topic__icontains=data["q"])
                | Q(consultation__teacher__first_name__icontains=data["q"])
                | Q(consultation__teacher__last_name__icontains=data["q"])
                | Q(consultation__teacher__username__icontains=data["q"])
            )
        ordering = {
            "date": ("consultation__starts_at", "pk"),
            "-date": ("-consultation__starts_at", "-pk"),
            "teacher": (
                "consultation__teacher__last_name",
                "consultation__starts_at",
                "pk",
            ),
        }
        bookings = bookings.order_by(*ordering.get(data["sort"], ordering["date"]))
    else:
        bookings = bookings.none()
    return render(
        request,
        "schedule/booking_list.html",
        {
            "form": form,
            "page_obj": Paginator(bookings, 10).get_page(request.GET.get("page")),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def booking_edit(request, booking_id=None):
    if request.user.role != User.Role.STUDENT:
        raise PermissionDenied("Записи создаёт и редактирует студент.")
    booking = None
    if booking_id is not None:
        booking = get_object_or_404(Booking.objects.with_details(), pk=booking_id)
        if booking.student_id != request.user.pk:
            raise PermissionDenied("Нельзя редактировать чужую запись.")
        if (
            booking.status != Booking.Status.ACTIVE
            or booking.consultation.starts_at <= timezone.now()
        ):
            messages.error(request, "Можно изменить только будущую активную запись.")
            return redirect(booking)
    form = BookingForm(
        request.POST if request.method == "POST" else None,
        instance=booking,
        student=request.user,
    )
    if request.method == "POST" and form.is_valid():
        try:
            saved = save_booking_form(form, request.user)
        except RuleError as exc:
            form.add_error(None, str(exc))
        except IntegrityError:
            form.add_error(None, "Время уже занято. Выберите другую консультацию.")
        else:
            messages.success(request, "Запись сохранена.")
            return redirect(saved)
    return render(
        request, "schedule/booking_form.html", {"form": form, "booking": booking}
    )


@login_required
@require_POST
def booking_cancel(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    try:
        cancel_booking(request.user, booking.pk)
    except RuleError as exc:
        if exc.status == 403:
            raise PermissionDenied(str(exc)) from exc
        messages.error(request, str(exc))
    else:
        messages.success(request, "Запись отменена. Время снова свободно.")
    return redirect(booking)


def consultation_detail(request, slug):
    slot = get_object_or_404(Consultation.objects.select_related("teacher"), slug=slug)
    available = slot.starts_at > timezone.now() and not slot.bookings.active().exists()
    return render(
        request,
        "schedule/consultation_detail.html",
        {"slot": slot, "available": available},
    )


@login_required
def statistics(request):
    bookings = Booking.objects.for_user(request.user)
    totals = bookings.aggregate(
        total=Count("pk"),
        active=Count("pk", filter=Q(status=Booking.Status.ACTIVE)),
        cancelled=Count("pk", filter=Q(status=Booking.Status.CANCELLED)),
        completed=Count("pk", filter=Q(status=Booking.Status.COMPLETED)),
        minutes=Sum("duration_minutes", default=0),
    )
    by_teacher = (
        bookings.order_by()
        .values(
            "consultation__teacher__username",
            "consultation__teacher__first_name",
            "consultation__teacher__last_name",
        )
        .annotate(total=Count("pk"))
        .order_by("-total", "consultation__teacher__username")
    )
    return render(
        request,
        "schedule/statistics.html",
        {"totals": totals, "by_teacher": by_teacher},
    )
