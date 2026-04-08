from rest_framework.routers import DefaultRouter
from .views import ApplicationViewSet, NotificationViewSet
from django.urls import path, include

router = DefaultRouter()
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"", ApplicationViewSet, basename="application")

urlpatterns = [
    path("", include(router.urls)),
]
