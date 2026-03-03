from django.contrib import admin, messages
from django.urls import reverse
from django.shortcuts import redirect
from django.utils.html import format_html
from .models import License
from applications.models import Application


class LicenseDuplicatesFilter(admin.SimpleListFilter):
    title = "duplicates"
    parameter_name = "has_duplicates"

    def lookups(self, request, model_admin):
        return (("yes", "Has duplicates"), ("no", "No duplicates"))

    def queryset(self, request, queryset):
        val = self.value()
        if not val:
            return queryset
        ids = []
        for lic in queryset:
            try:
                # owner/type duplicates
                c1 = queryset.model.objects.filter(owner=lic.owner, license_type=lic.license_type).exclude(pk=lic.pk).count()
                # license_number duplicates
                c2 = 0
                if lic.license_number:
                    c2 = queryset.model.objects.filter(license_number=lic.license_number).exclude(pk=lic.pk).count()
                has_dup = (c1 > 0) or (c2 > 0)
                if (val == "yes" and has_dup) or (val == "no" and not has_dup):
                    ids.append(lic.pk)
            except Exception:
                continue
        return queryset.filter(pk__in=ids)


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "license_type", "status", "duplicate_count_column", "created_at")
    list_filter = ("license_type", "status", LicenseDuplicatesFilter)
    search_fields = ("owner__username", "data")
    exclude = ("license_photo",)
    readonly_fields = ("preview_license_photo",)
    fields = (
        "owner",
        "license_type",
        "license_number",
        "issued_by",
        "issued_date",
        "expiry_date",
        "status",
        "data",
        "preview_license_photo",
    )
    actions = ("start_renewal", "start_grade_change", "start_name_change", "start_replacement")

    def preview_license_photo(self, obj):
        try:
            f = getattr(obj, "license_photo", None)
            url = getattr(f, "url", None)
            if url:
                return format_html('<img src="{}" style="max-width:200px; height:auto; border:1px solid #ddd;"/>', url)
        except Exception:
            pass
        try:
            app_id = None
            if isinstance(obj.data, dict):
                app_id = obj.data.get("application_id")
            app = None
            if app_id:
                app = Application.objects.filter(id=app_id).first()
            if not app:
                app = Application.objects.filter(applicant=obj.owner, license_type=obj.license_type).order_by("-created_at").first()
            if app:
                for fld in ("profile_photo", "professional_photo", "company_representative_photo"):
                    af = getattr(app, fld, None)
                    if af:
                        url = getattr(af, "url", None)
                        if url:
                            return format_html('<img src="{}" style="max-width:200px; height:auto; border:1px solid #ddd;"/>', url)
        except Exception:
            pass
        return "-"

    def _redirect_to_app(self, request, app):
        try:
            url = reverse("admin:applications_application_change", args=[app.pk])
            return redirect(url)
        except Exception:
            messages.success(request, f"Created application {app.id}")
            return None

    def start_renewal(self, request, queryset):
        if queryset.count() != 1:
            messages.error(request, "Select exactly one license to start renewal.")
            return
        lic = queryset.first()
        app = Application.objects.create(
            applicant=lic.owner,
            company=getattr(lic, "company", None),
            license_type=lic.license_type,
            subtype="company_renewal" if "contractor" in lic.license_type.lower() else "professional_renewal",
            data={"renewalPeriod": "1year"},
        )
        try:
            setattr(app, "is_renewal", True)
            setattr(app, "previous_license", lic)
            app.save()
        except Exception:
            pass
        Application.objects.filter(pk=app.pk).update(status="pending")
        return self._redirect_to_app(request, app)
    start_renewal.short_description = "Start renewal application"

    def start_grade_change(self, request, queryset):
        if queryset.count() != 1:
            messages.error(request, "Select exactly one license to start grade change.")
            return
        lic = queryset.first()
        app = Application.objects.create(
            applicant=lic.owner,
            company=getattr(lic, "company", None),
            license_type=lic.license_type,
            subtype="company_grade_change",
            data={"grade": "grade-a"},
        )
        return self._redirect_to_app(request, app)
    start_grade_change.short_description = "Start grade change application"

    def start_name_change(self, request, queryset):
        if queryset.count() != 1:
            messages.error(request, "Select exactly one license to start name change.")
            return
        lic = queryset.first()
        curr = None
        try:
            if isinstance(lic.data, dict):
                curr = lic.data.get("companyName") or lic.data.get("company_name")
        except Exception:
            curr = None
        app = Application.objects.create(
            applicant=lic.owner,
            company=getattr(lic, "company", None),
            license_type=lic.license_type,
            subtype="company_name_change",
            data={"companyName": curr or ""},
        )
        return self._redirect_to_app(request, app)
    start_name_change.short_description = "Start name change application"

    def start_replacement(self, request, queryset):
        if queryset.count() != 1:
            messages.error(request, "Select exactly one license to start replacement.")
            return
        lic = queryset.first()
        sub = "company_replacement" if "contractor" in lic.license_type.lower() else "professional_replacement"
        app = Application.objects.create(
            applicant=lic.owner,
            company=getattr(lic, "company", None),
            license_type=lic.license_type,
            subtype=sub,
            data={"replacementReason": "Lost"},
        )
        return self._redirect_to_app(request, app)
    start_replacement.short_description = "Start replacement application"

    def duplicate_count_column(self, obj):
        try:
            c1 = License.objects.filter(owner=obj.owner, license_type=obj.license_type).exclude(pk=obj.pk).count()
            c2 = 0
            if obj.license_number:
                c2 = License.objects.filter(license_number=obj.license_number).exclude(pk=obj.pk).count()
            total = c1 + c2
            if total > 0:
                return format_html('<span style="color:#b91c1c;font-weight:600;">{}</span>', total)
            return total
        except Exception:
            return "-"
    duplicate_count_column.short_description = "Dups"
