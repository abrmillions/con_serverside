from django.urls import path
from .views import system_settings_view

urlpatterns = [
    path("settings/", system_settings_view, name="system_settings"),
]
