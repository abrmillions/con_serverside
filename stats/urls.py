from django.urls import path
from .views import stats_view, admin_analytics_view

urlpatterns = [
    path("", stats_view, name="stats"),
    path("admin-dashboard/", admin_analytics_view, name="admin_dashboard"),
]
