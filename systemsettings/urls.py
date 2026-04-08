from django.urls import path
from .views import system_settings_view, maintenance_status_view, public_support_view

urlpatterns = [
    path("settings/", system_settings_view, name="system_settings"),
    path("maintenance/", maintenance_status_view, name="maintenance_status"),
    path("support/", public_support_view, name="support_public"),
]
