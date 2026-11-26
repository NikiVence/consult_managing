from django.contrib import admin
from django.urls import path
from schedule import api
from schedule import views
from django.conf import settings
from django.urls import include

urlpatterns = [
    path("accounts/login/", views.AccountLoginView.as_view(), name="login"),
    path("bookings/", views.booking_list, name="booking_list"),
    path("bookings/new/", views.booking_edit, name="booking_create"),
    path("bookings/<int:booking_id>/edit/", views.booking_edit, name="booking_edit"),
    path(
        "bookings/<int:booking_id>/cancel/", views.booking_cancel, name="booking_cancel"
    ),
    path(
        "consultations/<slug:slug>/",
        views.consultation_detail,
        name="consultation_detail",
    ),
    path("statistics/", views.statistics, name="statistics"),
    path("", api.home),
    path("admin/", admin.site.urls),
    path("bookings/<int:booking_id>/", api.booking_detail, name="booking_detail"),
    path("api/docs/", api.docs),
    path("api/openapi.json", api.openapi),
    path("api/csrf/", api.csrf_token),
    path("api/auth/register/", api.register),
    path("api/auth/login/", api.sign_in),
    path("api/auth/logout/", api.sign_out),
    path("api/auth/me/", api.me),
    path("api/consultations/", api.consultations),
    path("api/bookings/", api.bookings),
    path("api/bookings/<int:booking_id>/cancel/", api.cancel),
    path("health/live/", api.live),
    path("health/ready/", api.ready),
]
if settings.DEBUG_TOOLBAR:
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
