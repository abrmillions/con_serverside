from rest_framework.routers import DefaultRouter
from .views import DocumentViewSet
from django.urls import path, include

router = DefaultRouter()
router.register(r"", DocumentViewSet, basename="document")

urlpatterns = [
    # Alias for upload to match frontend expectation: POST /api/documents/upload/
    path("upload/", DocumentViewSet.as_view({"post": "create"}), name="document-upload"),
    path("", include(router.urls)),
]
