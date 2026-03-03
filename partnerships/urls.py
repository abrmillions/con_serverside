from rest_framework.routers import DefaultRouter
from .views import PartnershipViewSet, PartnershipPublicView, verify_partnership, verify_partnership_by_cert
from django.urls import path, include

router = DefaultRouter()
router.register(r"", PartnershipViewSet, basename="partnership")

urlpatterns = [
    path("<uuid:id>/public/", PartnershipPublicView.as_view(), name="partnership-public"),
    # Alias endpoint requested: GET /api/partnerships/verify/<uuid:id>/
    path("verify/<uuid:id>/", verify_partnership, name="partnership-verify"),
    path("verify-cert/<str:cert>/", verify_partnership_by_cert, name="partnership-verify-cert"),
    path("", include(router.urls)),
]
