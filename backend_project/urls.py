from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from partnerships.views import verify_single_document
from vehicles.views import verify_single_vehicle_document

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/users/", include("users.urls")),
    path("api/licenses/", include("licenses.urls")),
    path("api/vehicles/", include("vehicles.urls")),
    path("api/verify-pdoc/", verify_single_document, name="verify-single-pdoc-standalone"),
    path("api/verify-vdoc/", verify_single_vehicle_document, name="verify-single-vdoc-standalone"),
    path("api/partnerships/", include("partnerships.urls")),
    path("api/payments/", include("payments.urls")),
    path("api/applications/", include("applications.urls")),
    path("api/documents/", include("documents.urls")),
    path("api/stats/", include("stats.urls")),
    path("api/contact/", include("contact.urls")),
    path("api/system/", include("systemsettings.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
