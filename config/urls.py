from django.contrib import admin
from django.urls import path, include, re_path
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as media_serve
from partnerships.views import verify_single_document
from vehicles.views import verify_single_vehicle_document

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/users/", include("users.urls")),
    path("api/licenses/verify/", __import__("publicverify", fromlist=["verify_by_number"]).verify_by_number),
    path("api/licenses/", include("licenses.urls")),
    path("api/vehicles/", include("vehicles.urls")),
    path("api/verify-pdoc/", verify_single_document, name="verify-single-pdoc-standalone"),
    path("api/verify-vdoc/", verify_single_vehicle_document, name="verify-single-vdoc-standalone"),
    path("api/partnerships/", include("partnerships.urls")),
    path("api/payments/", include("payments.urls")),
    path("api/applications/", include("applications.urls")),
    path("api/documents/", include("documents.urls")),
    path("api/stats/", include("stats.urls")),
    path("api/system/", include("systemsettings.urls")),
    path("api/companies/", include("companies.urls")),
    path("api/contact/", include("contact.urls")),
    path("", lambda r: HttpResponse("Backend OK"), name="root"),
    path("health", lambda r: JsonResponse({"status": "ok"}), name="health"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', media_serve, {'document_root': settings.MEDIA_ROOT}),
    ]
