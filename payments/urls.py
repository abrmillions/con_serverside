from rest_framework.routers import DefaultRouter
from django.urls import path, include
from payments.views.legacy_views import PaymentViewSet
from payments.views.create_payment import create_payment
from payments.views.verify_payment import verify_payment
from payments.views.webhook import chapa_webhook

router = DefaultRouter()
router.register(r"", PaymentViewSet, basename="payment")

urlpatterns = [
    path("create/", create_payment, name="chapa_create_payment"),
    path("verify/<str:tx_ref>/", verify_payment, name="chapa_verify_payment"),
    path("webhook/", chapa_webhook, name="chapa_webhook"),
    path("manage/", include(router.urls)),
]
