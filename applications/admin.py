from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.utils.html import format_html
from django.http import HttpResponse
from django.utils.text import slugify
import io
import zipfile
from django import forms

from .models import Application, ApplicationLog
from documents.models import Document, DocumentAccessLog

class ApplicationAdminForm(forms.ModelForm):
    grade = forms.CharField(required=False, label="Grade")
    current_position = forms.CharField(required=False, label="Current Position")

    class Meta:
        model = Application
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            d = self.instance.data if isinstance(self.instance.data, dict) else {}
            raw = d.get("grade") or d.get("licenseType") or d.get("category") or d.get("permitDetails") or d.get("permit_details")
            self.fields["grade"].initial = raw
            pos = d.get("position") or d.get("currentPosition") or d.get("current_position")
            self.fields["current_position"].initial = pos
        except Exception:
            self.fields["grade"].initial = None
            self.fields["current_position"].initial = None

    def save(self, commit=True):
        inst = super().save(commit=False)
        try:
            d = inst.data if isinstance(inst.data, dict) else {}
            d = d or {}
            val = self.cleaned_data.get("grade")
            if val is not None and str(val).strip():
                g = str(val).strip().lower()
                if g in ("grade-a", "a", "grade 1", "grade1"):
                    d["grade"] = "Grade 1 - Large Projects"
                elif g in ("grade-b", "b", "grade 2", "grade2"):
                    d["grade"] = "Grade 2 - Medium Projects"
                elif g in ("grade-c", "c", "grade 3", "grade3"):
                    d["grade"] = "Grade 3 - Small Projects"
                elif g in ("specialized", "specialised", "specialized contractor", "specialised contractor"):
                    d["grade"] = "Specialized Contractor"
                else:
                    d["grade"] = val
                # Sync permitDetails for Import/Export applications
                if inst.license_type == "Import/Export License":
                    d["permitDetails"] = val
                    d["permit_details"] = val
            pos_val = self.cleaned_data.get("current_position")
            if pos_val is not None and str(pos_val).strip():
                d["position"] = str(pos_val).strip()
                d["currentPosition"] = d["position"]
                d["current_position"] = d["position"]
            inst.data = d
        except Exception:
            pass
        if commit:
            inst.save()
        return inst


class DocumentInline(admin.TabularInline):
    model = Document
    fields = ("name", "file_link", "uploaded_at")
    readonly_fields = ("file_link", "uploaded_at")
    extra = 0

    def file_link(self, obj):
        try:
            storage = obj.file.storage
            if not storage.exists(obj.file.name):
                return format_html('<span style="color: #c00;">Missing file</span>')
            return format_html('<a href="{}" target="_blank" rel="noopener">View</a>', obj.file.url)
        except Exception:
            return "-"


class ApplicationLogInline(admin.TabularInline):
    model = ApplicationLog
    readonly_fields = ("actor", "action", "details", "timestamp")
    extra = 0
    can_delete = False


class HasDuplicatesFilter(SimpleListFilter):
    title = "duplicates"
    parameter_name = "has_duplicates"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Has duplicates"),
            ("no", "No duplicates"),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if not val:
            return queryset
        from applications.models import Application
        ids = []
        if val == "yes":
            for app in queryset:
                cnt = Application.objects.filter(applicant=app.applicant, license_type=app.license_type).exclude(pk=app.pk).count()
                if cnt > 0:
                    ids.append(app.pk)
            return queryset.filter(pk__in=ids)
        if val == "no":
            for app in queryset:
                cnt = Application.objects.filter(applicant=app.applicant, license_type=app.license_type).exclude(pk=app.pk).count()
                if cnt == 0:
                    ids.append(app.pk)
            return queryset.filter(pk__in=ids)
        return queryset


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    form = ApplicationAdminForm
    list_display = ("id", "applicant", "company", "license_type", "grade_column", "current_position_column", "duplicate_app_count", "duplicate_license_count", "status", "created_at")
    list_filter = ("license_type", "status", "company", HasDuplicatesFilter)
    search_fields = ("applicant__email", "company__name", "company__registration_number")
    raw_id_fields = ("applicant", "company")
    inlines = (DocumentInline, ApplicationLogInline)
    actions = ("approve_applications", "reject_applications", "request_info_applications", "download_documents_zip", "link_companies_from_data", "duplicates_summary")
    exclude = ("profile_photo", "professional_photo", "company_representative_photo")
    readonly_fields = ("preview_certificate_photo",)
    fields = (
        "applicant",
        "company",
        "license_type",
        "subtype",
        "grade",
        "current_position",
        "status",
        "data",
        "preview_certificate_photo",
    )

    def link_companies_from_data(self, request, queryset):
        ok = 0
        for app in queryset:
            try:
                if not app.company and app.license_type == "Contractor License":
                    d = app.data if isinstance(app.data, dict) else {}
                    cname = (d.get("companyName") or d.get("company_name") or "").strip()
                    creg = (d.get("registrationNumber") or d.get("registration_number") or "").strip()
                    if cname or creg:
                        from companies.models import Company
                        company = None
                        if creg:
                            company = Company.objects.filter(registration_number=creg).first()
                        if not company and cname:
                            company = Company.objects.filter(name=cname).first()
                        if not company and cname:
                            company = Company.objects.create(
                                name=cname,
                                registration_number=creg or None,
                                contact_person=app.applicant,
                                email=(d.get('email') or None),
                                phone=(d.get('phone') or None),
                                address=(d.get('address') or None),
                                city=(d.get('city') or None),
                                state=(d.get('state') or None),
                                zip_code=(d.get('postalCode') or d.get('zip_code') or None),
                                website=(d.get('website') or None),
                            )
                        if company:
                            app.company = company
                            app.save(update_fields=["company"])
                            ok += 1
            except Exception:
                continue
        if ok:
            messages.success(request, f"Linked companies for {ok} application(s)")
    link_companies_from_data.short_description = "Link/create Company from application data"

    def approve_applications(self, request, queryset):
        ok = 0
        for app in queryset:
            try:
                app.status = "approved"
                app.save(update_fields=["status"])
                try:
                    ApplicationLog.objects.create(application=app, actor=request.user, action="approved", details="Approved via admin action")
                except Exception:
                    pass
                # Persist side effects in save_model
                self.save_model(request, app, form=None, change=True)
                ok += 1
            except Exception:
                continue
        if ok:
            messages.success(request, f"Approved {ok} application(s)")
    approve_applications.short_description = "Approve selected applications"

    def duplicates_summary(self, request, queryset):
        from applications.models import Application
        from licenses.models import License
        total = queryset.count()
        dup_apps = 0
        dup_lics = 0
        for app in queryset:
            try:
                c1 = Application.objects.filter(applicant=app.applicant, license_type=app.license_type).exclude(pk=app.pk).count()
                if c1 > 0:
                    dup_apps += 1
                c2 = License.objects.filter(owner=app.applicant, license_type=app.license_type).exclude().count()
                # also count duplicate license_number collisions for same owner/type
                try:
                    if c2 <= 1:
                        if app.data and isinstance(app.data, dict):
                            ln = app.data.get("licenseNumber") or app.data.get("license_number")
                            if ln:
                                c2 = License.objects.filter(license_number=ln).count()
                except Exception:
                    pass
                if c2 > 1:
                    dup_lics += 1
            except Exception:
                continue
        messages.info(request, f"Duplicate summary for {total} selection — applications with duplicates: {dup_apps}, licenses with duplicates: {dup_lics}")
    duplicates_summary.short_description = "Show duplicate summary for selected"

    def reject_applications(self, request, queryset):
        ok = 0
        for app in queryset:
            try:
                app.status = "rejected"
                app.save(update_fields=["status"])
                try:
                    ApplicationLog.objects.create(application=app, actor=request.user, action="rejected", details="Rejected via admin action")
                except Exception:
                    pass
                ok += 1
            except Exception:
                continue
        if ok:
            messages.success(request, f"Rejected {ok} application(s)")
    reject_applications.short_description = "Reject selected applications"

    def request_info_applications(self, request, queryset):
        ok = 0
        for app in queryset:
            try:
                app.status = "info_requested"
                data = app.data if isinstance(app.data, dict) else {}
                try:
                    data["infoRequested"] = True
                except Exception:
                    pass
                app.data = data
                app.save(update_fields=["status", "data"])
                try:
                    ApplicationLog.objects.create(application=app, actor=request.user, action="info_requested", details="More information requested via admin action")
                except Exception:
                    pass
                ok += 1
            except Exception:
                continue
        if ok:
            messages.success(request, f"Marked {ok} application(s) as info requested")
    request_info_applications.short_description = "Request more information"

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        try:
            company_id = request.GET.get("company")
            license_type = request.GET.get("license_type")
            if company_id:
                initial["company"] = company_id
            if license_type:
                initial["license_type"] = license_type
        except Exception:
            pass
        return initial

    def save_model(self, request, obj, form, change):
        prev_status = None
        if obj.pk:
            try:
                prev = Application.objects.get(pk=obj.pk)
                prev_status = prev.status
            except Application.DoesNotExist:
                prev_status = None
        super().save_model(request, obj, form, change)
        try:
            # Ensure Company is linked early based on application data for contractor flows
            if not obj.company and obj.license_type == "Contractor License":
                d = obj.data if isinstance(obj.data, dict) else {}
                cname = (d.get("companyName") or d.get("company_name") or "").strip()
                creg = (d.get("registrationNumber") or d.get("registration_number") or "").strip()
                if cname or creg:
                    from companies.models import Company
                    company = None
                    if creg:
                        company = Company.objects.filter(registration_number=creg).first()
                    if not company and cname:
                        company = Company.objects.filter(name=cname).first()
                    if not company and cname:
                        company = Company.objects.create(
                            name=cname,
                            registration_number=creg or None,
                            contact_person=obj.applicant,
                            email=(d.get('email') or None),
                            phone=(d.get('phone') or None),
                            address=(d.get('address') or None),
                            city=(d.get('city') or None),
                            state=(d.get('state') or None),
                            zip_code=(d.get('postalCode') or d.get('zip_code') or None),
                            website=(d.get('website') or None),
                        )
                    if company:
                        obj.company = company
                        obj.save(update_fields=["company"])
            if obj.status == "approved":
                from datetime import date
                from licenses.models import License
                today = date.today()
                year = today.year
                prefix = "LIC"
                license_qs = License.objects.filter(owner=obj.applicant, license_type=obj.license_type)
                lic = None
                if license_qs.exists():
                    lic = license_qs.first()
                    license_number = lic.license_number or ""
                else:
                    seq = License.objects.count() + 1
                    while True:
                        candidate = f"{prefix}-{year:04d}-{seq:06d}"
                        if not License.objects.filter(license_number=candidate).exists():
                            license_number = candidate
                            break
                        seq += 1
                expiry = date(today.year + 5, today.month, today.day)
                base_data = obj.data if isinstance(obj.data, dict) else {}
                company_name = None
                if isinstance(base_data, dict):
                    cn = base_data.get("companyName") or base_data.get("company_name") or base_data.get("company")
                    if cn and isinstance(cn, str):
                        company_name = cn.strip()
                merged_data = {
                    **(base_data or {}),
                    "subtype": obj.subtype,
                    "licenseNumber": license_number,
                    "issueDate": today.isoformat(),
                    "expiryDate": expiry.isoformat(),
                    "application_id": obj.id,
                }
                if company_name and not merged_data.get("companyName"):
                    merged_data["companyName"] = company_name
                try:
                    if obj.license_type == "Professional License":
                        pos = None
                        if isinstance(base_data, dict):
                            pos = base_data.get("position") or base_data.get("currentPosition") or base_data.get("current_position")
                        if pos:
                            merged_data["position"] = str(pos).strip()
                            merged_data["currentPosition"] = merged_data["position"]
                            merged_data["current_position"] = merged_data["position"]
                except Exception:
                    pass
                if lic is None:
                    lic = License.objects.create(
                        owner=obj.applicant,
                        license_type=obj.license_type,
                        license_number=license_number,
                        issued_by=request.user,
                        issued_date=today,
                        expiry_date=expiry,
                        data=merged_data,
                        status="active",
                        company=obj.company,
                    )
                else:
                    lic.issued_by = lic.issued_by or request.user
                    lic.issued_date = lic.issued_date or today
                    lic.expiry_date = lic.expiry_date or expiry
                    if not getattr(lic, "company", None) and getattr(obj, "company", None):
                        lic.company = obj.company
                    new_data = lic.data if isinstance(lic.data, dict) else {}
                    new_data.update(merged_data)
                    lic.data = new_data
                    if lic.status in ("pending", "approved"):
                        lic.status = "active"
                    lic.save()
                    candidates = []
                    if obj.license_type == "Contractor License":
                        candidates.append(obj.profile_photo)
                    elif obj.license_type == "Professional License":
                        candidates.append(obj.professional_photo)
                    elif obj.license_type == "Import/Export License":
                        candidates.append(obj.company_representative_photo)
                    candidates.extend([obj.profile_photo, obj.professional_photo, obj.company_representative_photo])
                    photo_field = next((f for f in candidates if f), None)
                    if photo_field and getattr(photo_field, "name", None):
                        from django.core.files.base import ContentFile
                        import os
                        try:
                            photo_field.open("rb")
                            try:
                                name = os.path.basename(photo_field.name)
                                content = photo_field.read()
                                lic.license_photo.save(name, ContentFile(content))
                            finally:
                                try:
                                    photo_field.close()
                                except Exception:
                                    pass
                        except Exception:
                            try:
                                lic.license_photo = photo_field
                            except Exception:
                                pass
                        lic.save(update_fields=["license_photo"])
                    else:
                        try:
                            docs = getattr(obj, "documents", None)
                            chosen = None
                            if docs:
                                for doc in docs.all():
                                    f = getattr(doc, "file", None)
                                    name = getattr(f, "name", "")
                                    if isinstance(name, str) and name.lower().split(".")[-1] in ("jpg", "jpeg", "png", "gif", "webp"):
                                        chosen = f
                                        break
                            if chosen:
                                from django.core.files.base import ContentFile
                                import os
                                storage = chosen.storage
                                fh = None
                                try:
                                    fh = storage.open(chosen.name, "rb")
                                    content = fh.read()
                                    basename = os.path.basename(chosen.name)
                                    lic.license_photo.save(basename, ContentFile(content))
                                    lic.save(update_fields=["license_photo"])
                                finally:
                                    try:
                                        if fh:
                                            fh.close()
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                    try:
                        app_data = obj.data if isinstance(obj.data, dict) else {}
                        app_data["licenseNumber"] = license_number
                        app_data["license_number"] = license_number
                        obj.data = app_data
                        obj.save(update_fields=["data"])
                    except Exception:
                        pass
                    try:
                        if prev_status != "approved":
                            ApplicationLog.objects.create(
                                application=obj,
                                actor=request.user,
                                action="approved",
                                details="Approved via admin",
                            )
                    except Exception:
                        pass
        except Exception:
            pass

    def preview_certificate_photo(self, obj):
        try:
            candidates = []
            if obj.license_type == "Contractor License":
                candidates.append(obj.profile_photo)
            elif obj.license_type == "Professional License":
                candidates.append(obj.professional_photo)
            elif obj.license_type == "Import/Export License":
                candidates.append(obj.company_representative_photo)
            candidates.extend([obj.profile_photo, obj.professional_photo, obj.company_representative_photo])
            for f in candidates:
                if f:
                    url = getattr(f, "url", None)
                    if url:
                        return format_html('<img src="{}" style="max-width:200px; height:auto; border:1px solid #ddd;"/>', url)
            try:
                from licenses.models import License
                lic = License.objects.filter(owner=obj.applicant, license_type=obj.license_type).order_by("-issued_date").first()
                if lic and getattr(lic, "license_photo", None):
                    url = getattr(lic.license_photo, "url", None)
                    if url:
                        return format_html('<img src="{}" style="max-width:200px; height:auto; border:1px solid #ddd;"/>', url)
            except Exception:
                pass
        except Exception:
            pass
        return "-"

    preview_certificate_photo.short_description = "Certificate Photo"

    def current_position_column(self, obj):
        try:
            d = obj.data if isinstance(obj.data, dict) else {}
            val = d.get("position") or d.get("currentPosition") or d.get("current_position")
            return val or "-"
        except Exception:
            return "-"
    current_position_column.short_description = "Current Position"

    def duplicate_app_count(self, obj):
        try:
            from applications.models import Application
            cnt = Application.objects.filter(applicant=obj.applicant, license_type=obj.license_type).exclude(pk=obj.pk).count()
            if cnt > 0:
                return format_html('<span style="color:#b91c1c;font-weight:600;">{}</span>', cnt)
            return cnt
        except Exception:
            return "-"
    duplicate_app_count.short_description = "App Dups"

    def duplicate_license_count(self, obj):
        try:
            from licenses.models import License
            # duplicates by license_number or multiple owner/type (should be 1)
            c_owner_type = License.objects.filter(owner=obj.applicant, license_type=obj.license_type).count()
            dup = max(0, c_owner_type - 1)
            ln = None
            if isinstance(obj.data, dict):
                ln = obj.data.get("licenseNumber") or obj.data.get("license_number")
            if ln:
                dup_ln = max(0, License.objects.filter(license_number=ln).count() - 1)
                dup += dup_ln
            if dup > 0:
                return format_html('<span style="color:#b45309;font-weight:600;">{}</span>', dup)
            return dup
        except Exception:
            return "-"
    duplicate_license_count.short_description = "License Dups"
    def grade_column(self, obj):
        try:
            if obj.license_type != "Contractor License":
                return "-"
            d = obj.data if isinstance(obj.data, dict) else {}
            raw = d.get("grade") or d.get("licenseType") or d.get("category") or ""
            if not str(raw).strip():
                return "-"
            s = str(raw).strip().lower()
            if s in ("grade-a", "a", "grade 1", "grade1"):
                return "Grade 1 - Large Projects"
            if s in ("grade-b", "b", "grade 2", "grade2"):
                return "Grade 2 - Medium Projects"
            if s in ("grade-c", "c", "grade 3", "grade3"):
                return "Grade 3 - Small Projects"
            if s in ("specialized", "specialised", "specialized contractor", "specialised contractor"):
                return "Specialized Contractor"
            return str(raw)
        except Exception:
            return "-"
    grade_column.short_description = "Grade"

    def download_documents_zip(self, request, queryset):
        """Admin action: create a zip of all documents for selected applications and return it as a response."""
        buffer = io.BytesIO()
        z = zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED)
        files_added = 0

        for app in queryset.select_related("applicant").prefetch_related("documents"):
            applicant_email = app.applicant.email if app.applicant else f"app_{app.id}"
            folder = slugify(applicant_email)
            for doc in app.documents.all():
                try:
                    # ensure file exists
                    storage = doc.file.storage
                    if not storage.exists(doc.file.name):
                        continue
                    with storage.open(doc.file.name, "rb") as fh:
                        data = fh.read()
                    arcname = f"{folder}/{doc.name or doc.file.name}"
                    z.writestr(arcname, data)
                    files_added += 1
                    # Log access
                    try:
                        DocumentAccessLog.objects.create(
                            user=request.user if request.user.is_authenticated else None,
                            document=doc,
                            application=app,
                            action="download",
                            details=f"Downloaded as part of admin zip for application {app.id}",
                        )
                    except Exception:
                        pass
                except Exception:
                    # skip any unreadable files
                    continue

        z.close()
        if files_added == 0:
            self.message_user(request, "No documents available to download for selected applications.")
            return None

        buffer.seek(0)
        resp = HttpResponse(buffer.getvalue(), content_type="application/zip")
        resp["Content-Disposition"] = "attachment; filename=applications_documents.zip"
        return resp

    download_documents_zip.short_description = "Download documents for selected applications (zip)"

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        try:
            obj = form.instance
            for fs in formsets:
                try:
                    if fs.model is Document:
                        for inst in fs.queryset.all():
                            if not getattr(inst, "uploader_id", None):
                                inst.uploader = request.user if request.user.is_authenticated else None
                                inst.save(update_fields=["uploader"])
                except Exception:
                    continue
        except Exception:
            pass
