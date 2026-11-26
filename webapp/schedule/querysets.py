from django.db import models


class BookingQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status="active")

    def with_details(self):
        return self.select_related("student", "consultation__teacher")

    def for_user(self, user):
        if user.role == "teacher":
            return self.filter(consultation__teacher=user)
        return self.filter(student=user)

    def on_date(self, day):
        return self.filter(consultation__starts_at__date=day)
