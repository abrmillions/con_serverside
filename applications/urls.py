from rest_framework.routers import DefaultRouter
from .views import ApplicationViewSet
from django.urls import path, include

router = DefaultRouter()
router.register(r"", ApplicationViewSet, basename="application")

urlpatterns = [
    path("", include(router.urls)),
]
