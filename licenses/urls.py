from rest_framework.routers import DefaultRouter
from .views import LicenseViewSet, LicenseQRGenerationView, LicenseVerificationView, LicenseDownloadView, LicenseRenewalsList, LicenseRenewalApproveView, LicenseRenewalRejectView
from django.urls import path, include

router = DefaultRouter()
router.register(r"", LicenseViewSet, basename="license")

# IMPORTANT: Put explicit custom endpoints (qr / verify / download)
# BEFORE the router include, otherwise the router will try to treat
# "verify" as a primary key and DRF will return a generic "Not found."
urlpatterns = [
    path("qr/", LicenseQRGenerationView.as_view(), name='license-qr-generation'),
    path("verify/", LicenseVerificationView.as_view(), name='license-verification'),
    # Public alias to avoid any router conflicts in some environments
    path("public/verify/", LicenseVerificationView.as_view(), name='license-verification-public'),
    path("verify-number/", LicenseVerificationView.as_view(), name='license-verification-number'),
    path("download/<int:pk>/", LicenseDownloadView.as_view(), name='license-download'),
    path("renewals/", LicenseRenewalsList.as_view(), name='license-renewals'),
    path("renewals/<int:pk>/approve/", LicenseRenewalApproveView.as_view(), name='license-renewal-approve'),
    path("renewals/<int:pk>/reject/", LicenseRenewalRejectView.as_view(), name='license-renewal-reject'),
    path("", include(router.urls)),
]
