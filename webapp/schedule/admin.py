from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from .models import Booking, Consultation, User
from .services import RuleError, cancel_booking, invalidate_schedule


class ConsultationAdminForm(forms.ModelForm):
    class Meta:
        model = Consultation
        fields = "__all__"

    def clean(self):
        data = super().clean()
        teacher = data.get("teacher")
        if teacher and teacher.role != User.Role.TEACHER:
            self.add_error("teacher", "Выберите преподавателя.")
        if self.instance.pk and self.instance.bookings.exists():
            if {"teacher", "starts_at"}.intersection(self.changed_data):
                raise ValidationError(
                    "У консультации есть записи: время и преподавателя менять нельзя."
                )
        elif data.get("starts_at") and data["starts_at"] <= timezone.now():
            self.add_error("starts_at", "Выберите будущее время.")
        return data


class BookingInline(admin.TabularInline):
    model = Booking
    extra = 0
    fields = ("student", "duration_minutes", "status", "ends_at")
    readonly_fields = fields
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(User)
class AccountAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Учебная роль", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Учебная роль", {"fields": ("role",)}),)
    list_display = ("username", "first_name", "last_name", "role", "is_staff")
    list_filter = UserAdmin.list_filter + ("role",)

    def get_readonly_fields(self, request, obj=None):
        if obj and (obj.slots.exists() or obj.bookings.exists()):
            return (*super().get_readonly_fields(request, obj), "role")
        return super().get_readonly_fields(request, obj)


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    form = ConsultationAdminForm
    list_display = ("topic", "teacher", "starts_at", "location", "booking_count")
    list_filter = ("teacher", "starts_at")
    search_fields = ("topic", "location", "teacher__username", "teacher__last_name")
    ordering = ("starts_at", "pk")
    list_select_related = ("teacher",)
    date_hierarchy = "starts_at"
    readonly_fields = ("slug",)
    autocomplete_fields = ("teacher",)
    inlines = (BookingInline,)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(total_bookings=Count("bookings"))

    @admin.display(description="Записей", ordering="total_bookings")
    def booking_count(self, obj):
        return obj.total_bookings

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        transaction.on_commit(invalidate_schedule)

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        transaction.on_commit(invalidate_schedule)

    def delete_queryset(self, request, queryset):
        super().delete_queryset(request, queryset)
        transaction.on_commit(invalidate_schedule)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "student",
        "consultation",
        "duration_minutes",
        "status",
        "ends_at",
    )
    list_filter = ("status", "consultation__teacher", "created_at")
    search_fields = ("student__username", "student__last_name", "consultation__topic")
    list_select_related = ("student", "consultation__teacher")
    ordering = ("-created_at", "-pk")
    readonly_fields = (
        "student",
        "consultation",
        "duration_minutes",
        "ends_at",
        "status",
        "created_at",
    )
    actions = ("cancel_selected", "complete_selected")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Отменить выбранные записи", permissions=["change"])
    def cancel_selected(self, request, queryset):
        count = 0
        for booking in queryset.active().select_related("student"):
            try:
                cancel_booking(booking.student, booking.pk)
                count += 1
            except RuleError as exc:
                self.message_user(request, str(exc), messages.WARNING)
        self.message_user(request, f"Отменено записей: {count}.")

    @admin.action(description="Завершить прошедшие встречи", permissions=["change"])
    def complete_selected(self, request, queryset):
        with transaction.atomic():
            count = (
                queryset.active()
                .filter(ends_at__lte=timezone.now())
                .update(status=Booking.Status.COMPLETED)
            )
            transaction.on_commit(invalidate_schedule)
        self.message_user(
            request, f"Завершено встреч: {count}. Будущие встречи не изменены."
        )


admin.site.site_header = "Консультант — управление"
admin.site.site_title = "Консультант"
admin.site.index_title = "Учебные консультации"
