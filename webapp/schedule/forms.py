from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Booking, Consultation, User
from .services import RuleError, validate_reservation


class BookingFilterForm(forms.Form):
    q = forms.CharField(label="Тема или преподаватель", required=False, max_length=100)
    date_from = forms.DateField(
        label="С даты", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    date_to = forms.DateField(
        label="По дату", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    teacher = forms.ModelChoiceField(
        label="Преподаватель",
        required=False,
        queryset=User.objects.filter(role=User.Role.TEACHER).order_by(
            "last_name", "pk"
        ),
        empty_label="Все преподаватели",
    )
    status = forms.ChoiceField(
        label="Статус",
        required=False,
        choices=[("", "Все статусы"), *Booking.Status.choices],
    )
    sort = forms.ChoiceField(
        label="Сортировка",
        required=False,
        choices=[
            ("date", "Ближайшие сначала"),
            ("-date", "Поздние сначала"),
            ("teacher", "По преподавателю"),
        ],
    )

    def clean(self):
        data = super().clean()
        start, end = data.get("date_from"), data.get("date_to")
        if start and end and start > end:
            raise ValidationError("Начало периода не может быть позже конца.")
        return data


class BookingForm(forms.ModelForm):
    duration_minutes = forms.IntegerField(
        label="Длительность, минут",
        min_value=15,
        max_value=90,
        help_text="От 15 до 90 минут. Пересечения встреч не допускаются.",
        widget=forms.NumberInput(attrs={"min": 15, "max": 90, "class": "form-control"}),
    )

    class Meta:
        model = Booking
        fields = ("consultation", "duration_minutes")
        labels = {"consultation": "Консультация"}
        widgets = {"consultation": forms.Select(attrs={"class": "form-select"})}

    def __init__(self, *args, student, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student
        self.fields["consultation"].queryset = Consultation.objects.filter(
            starts_at__gt=timezone.now(), teacher__role=User.Role.TEACHER
        ).select_related("teacher")

    def clean_consultation(self):
        slot = self.cleaned_data["consultation"]
        if slot.starts_at <= timezone.now():
            raise ValidationError("Выберите будущую консультацию.")
        return slot

    def clean(self):
        data = super().clean()
        slot, duration = data.get("consultation"), data.get("duration_minutes")
        if slot and duration is not None:
            try:
                validate_reservation(self.student, slot, duration, self.instance.pk)
            except RuleError as exc:
                raise ValidationError(str(exc)) from exc
        return data
