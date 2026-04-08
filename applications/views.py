from rest_framework import viewsets, permissions, decorators, response, status
from datetime import date
from django.utils.text import slugify
from django.http import HttpResponse
from .notifications import send_application_notification
import io
import zipfile
import os
import base64

from .models import Application, ApplicationLog, Notification
from .serializers import ApplicationSerializer, NotificationSerializer
from licenses.models import License
from licenses.serializers import LicenseSerializer
from documents.models import DocumentAccessLog, Document
from .verification import perform_verification
from django.utils import timezone
from django.urls import reverse
from django.core.mail import send_mail
from documents.utils import infer_document_name
import logging

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None
try:
    from PIL import Image
except Exception:
    Image = None
try:
    from google import genai as genai_new
    from google.genai import types as genai_types
except Exception:
    genai_new = None
    genai_types = None


class IsApplicantOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.applicant == request.user or request.user.is_staff


class ApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated, IsApplicantOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Application.objects.all().order_by("-created_at")
        return Application.objects.filter(applicant=user).order_by("-created_at")

    def create(self, request, *args, **kwargs):
        user = request.user
        requested_type = None
        logger.info(f"User {user.email} is creating a new application.")
        try:
            if isinstance(request.data, dict):
                requested_type = request.data.get('license_type')
                # Normalize data from FormData where 'data' may come as a JSON string or list
                dd = request.data.get('data')
                if isinstance(dd, (list, tuple)):
                    dd = dd[0] if dd else None
                if isinstance(dd, str):
                    try:
                        import json
                        dd = json.loads(dd)
                    except Exception:
                        dd = None
                is_renewal = bool(request.data.get('is_renewal')) or (bool(dd.get('is_renewal')) if isinstance(dd, dict) else False)
                if is_renewal:
                    return super().create(request, *args, **kwargs)
                subtype_val = request.data.get('subtype')
                if not subtype_val and isinstance(dd, dict):
                    subtype_val = dd.get('subtype')
                subtype_lc = (str(subtype_val or '')).lower().strip()
                allowed_subtypes = {
                    'company_grade_change',
                    'grade_change',
                    'company_grade_upgrade',
                    'change_grade',
                    'company_name_change',
                    'name_change',
                    'company_replacement',
                    'professional_replacement',
                    'replacement',
                }
                requested_type_lc = (str(requested_type or '')).lower()
                is_contractor_or_prof = ('contractor' in requested_type_lc) or ('professional' in requested_type_lc)
                bypass_checks = is_contractor_or_prof and (subtype_lc in allowed_subtypes)

            if not requested_type:
                if License.objects.filter(owner=user).exists():
                    if not bypass_checks:
                        return response.Response({"detail": "You already have a license and cannot create another application without specifying a license_type."}, status=status.HTTP_403_FORBIDDEN)
            else:
                # Allow multiple applications regardless of existing licenses or applications
                pass

            return super().create(request, *args, **kwargs)
        except Exception as e:
            return response.Response({"detail": f"Failed to create application: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer):
        # Normalize subtype: accept top-level `subtype` or `data.subtype` and persist to model.field
        data = serializer.validated_data.get('data') if hasattr(serializer, 'validated_data') else None
        if isinstance(data, str):
            try:
                import json
                data = json.loads(data)
                serializer.validated_data['data'] = data
            except Exception:
                pass
        # Normalize grade into data for contractor applications
        try:
            if not isinstance(data, dict):
                data = {} if data is None else {"value": data}
            # Accept top-level grade field
            if isinstance(self.request.data, dict):
                top_grade = self.request.data.get('grade')
                if isinstance(top_grade, (str, int)) and str(top_grade).strip():
                    data['grade'] = top_grade
            # If only category/licenseType present, copy to grade
            if not data.get('grade'):
                ltval = data.get('licenseType') or data.get('category')
                if ltval:
                    data['grade'] = ltval
            try:
                g = str(data.get('grade') or '').strip().lower()
                if g in ('grade-a', 'a', 'grade 1', 'grade1'):
                    data['grade'] = 'Grade 1 - Large Projects'
                elif g in ('grade-b', 'b', 'grade 2', 'grade2'):
                    data['grade'] = 'Grade 2 - Medium Projects'
                elif g in ('grade-c', 'c', 'grade 3', 'grade3'):
                    data['grade'] = 'Grade 3 - Small Projects'
                elif g in ('specialized', 'specialised', 'specialized contractor', 'specialised contractor'):
                    data['grade'] = 'Specialized Contractor'
            except Exception:
                pass
            # Persist normalized data back
            serializer.validated_data['data'] = data
        except Exception:
            pass
        subtype = None
        # check request data first
        if isinstance(self.request.data, dict):
            subtype = self.request.data.get('subtype')
            if not subtype:
                dd = self.request.data.get('data')
                if isinstance(dd, str):
                    try:
                        import json
                        dd = json.loads(dd)
                    except Exception:
                        dd = None
                if isinstance(dd, dict):
                    subtype = dd.get('subtype')

        # fallback to serializer validated data
        if not subtype and data:
            subtype = data.get('subtype')

        # Auto-assign subtype for common flows when not provided
        try:
            lt = serializer.validated_data.get('license_type') or getattr(serializer.instance, 'license_type', None)
            if not subtype and lt == "Contractor License":
                # Treat as new company registration by default
                subtype = "company_new"
        except Exception:
            pass

        # Attempt to attach a known company if present in payload; creation deferred to approval
        save_kwargs = {'applicant': self.request.user}
        try:
            lt = serializer.validated_data.get('license_type') or getattr(serializer.instance, 'license_type', None)
            if isinstance(data, dict):
                cname = (data.get('companyName') or data.get('company_name') or '').strip()
                creg = (data.get('registrationNumber') or data.get('registration_number') or '').strip()
                if cname or creg:
                    from companies.models import Company
                    company = None
                    # Prefer lookup by registration number, then by name
                    if creg:
                        company = Company.objects.filter(registration_number=creg).first()
                    if not company and cname:
                        company = Company.objects.filter(name=cname).first()
                    # If still not found and this is a Contractor License, create a stub company now
                    if not company and lt == "Contractor License" and cname:
                        company = Company.objects.create(
                            name=cname,
                            registration_number=creg or None,
                            contact_person=self.request.user,
                            email=(data.get('email') or None),
                            phone=(data.get('phone') or None),
                            address=(data.get('address') or None),
                            city=(data.get('city') or None),
                            state=(data.get('state') or None),
                            zip_code=(data.get('postalCode') or data.get('zip_code') or None),
                            website=(data.get('website') or None),
                        )
                    if company:
                        save_kwargs['company'] = company
        except Exception:
            pass

        if subtype:
            serializer.save(subtype=subtype, **save_kwargs)
        else:
            serializer.save(**save_kwargs)

    def update(self, request, *args, **kwargs):
        """Prevent changing uploaded photos once application is no longer pending."""
        instance = self.get_object()
        # Disallow staff/admin from uploading or modifying applicant photos at any time
        photo_fields = ('profile_photo', 'professional_photo', 'company_representative_photo')
        has_photo_update = any(f in request.data or f in request.FILES for f in photo_fields)
        if has_photo_update and request.user.is_staff and request.user != instance.applicant:
            return response.Response({"detail": "Admins cannot upload or modify applicant photos."}, status=status.HTTP_403_FORBIDDEN)
        # If application is not pending, disallow updates to photo fields for all users
        if instance.status != 'pending' and has_photo_update:
            return response.Response({"detail": "Cannot modify uploaded photos after application review."}, status=status.HTTP_403_FORBIDDEN)

        return super().update(request, *args, **kwargs)

    @decorators.action(detail=False, methods=["get"])
    def stats(self, request):
        if not request.user.is_staff:
             return response.Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        
        today = date.today()
        qs = Application.objects.all()
        
        pending_count = qs.filter(status="pending").count()
        under_review_count = qs.filter(status__in=["info_requested", "resubmitted"]).count()
        
        approved_today_count = ApplicationLog.objects.filter(
            action="approved", 
            timestamp__date=today
        ).count()

        return response.Response({
            "pending": pending_count,
            "under_review": under_review_count,
            "approved_today": approved_today_count
        })

    @decorators.action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        app = self.get_object()
        # Only staff/admin users may approve applications
        if not request.user.is_staff and not request.user.is_superuser:
            return response.Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        # If renewal, require payment verification flag in data
        try:
            dd = app.data if isinstance(app.data, dict) else {}
            if app.is_renewal and not dd.get("paymentVerified"):
                return response.Response({"detail": "Payment not verified for renewal."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            pass

        # Create or update Company (for contractor/company flows) and License for applicant
        license_data = app.data or {}

        # Generate a unique, human‑readable license number compatible with verification
        today = date.today()
        year = today.year
        prefix = "LIC"
        seq = License.objects.count() + 1
        while True:
            candidate = f"{prefix}-{year:04d}-{seq:06d}"
            if not License.objects.filter(license_number=candidate).exists():
                license_number = candidate
                break
            seq += 1

        # Compute expiry: for renewals, extend from previous expiry by selected years; otherwise default window
        expiry = date(today.year + 5, today.month, today.day)
        if app.is_renewal:
            try:
                base = getattr(app, 'previous_license', None)
                base_date = getattr(base, 'expiry_date', None) or today
                rp = None
                try:
                    dd = app.data if isinstance(app.data, dict) else {}
                    rp = dd.get('renewalPeriod') or dd.get('renewal_period')
                except Exception:
                    rp = None
                years = 1
                if isinstance(rp, (int, float)) and rp:
                    years = int(rp)
                elif isinstance(rp, str):
                    import re
                    m = re.search(r'(\d+)', rp)
                    if m:
                        years = int(m.group(1))
                expiry = date(base_date.year + max(1, years), base_date.month, base_date.day)
            except Exception:
                expiry = date(today.year + 1, today.month, today.day)

        base_data = license_data if isinstance(license_data, dict) else {}
        # Normalize company name into a consistent key
        try:
            company_name = None
            if isinstance(base_data, dict):
                company_name = base_data.get('companyName') or base_data.get('company_name') or base_data.get('company')
                if company_name and isinstance(company_name, str):
                    company_name = company_name.strip()
        except Exception:
            company_name = None

        # For contractor/company registration, ensure a Company record exists and link it
        company_obj = None
        try:
            if app.license_type == "Contractor License":
                from companies.models import Company
                reg_no = None
                if isinstance(base_data, dict):
                    reg_no = (base_data.get('registrationNumber') or base_data.get('registration_number') or '').strip() or None
                # Prefer lookup by registration_number when available
                q = None
                if reg_no:
                    q = Company.objects.filter(registration_number=reg_no).first()
                if not q and company_name:
                    q = Company.objects.filter(name=company_name).first()
                if not q:
                    q = Company.objects.create(
                        name=company_name or (getattr(app.applicant, 'email', 'Company')),
                        registration_number=reg_no,
                        address=(base_data.get('address') or ''),
                        city=(base_data.get('city') or ''),
                        state=(base_data.get('state') or ''),
                        zip_code=(base_data.get('postalCode') or base_data.get('zip_code') or ''),
                        phone=(base_data.get('phone') or ''),
                        email=(base_data.get('email') or ''),
                        website=(base_data.get('website') or ''),
                        contact_person=app.applicant,
                    )
                company_obj = q
                # Link to application if not already set
                try:
                    if not app.company:
                        app.company = q
                        app.save(update_fields=['company'])
                except Exception:
                    pass
        except Exception:
            company_obj = None
        issue_dt = today
        if app.is_renewal:
            try:
                base = getattr(app, 'previous_license', None)
                base_date = getattr(base, 'expiry_date', None)
                if base_date:
                    issue_dt = base_date
            except Exception:
                issue_dt = today
        merged_data = {
            **base_data,
            "subtype": app.subtype,
            "licenseNumber": license_number,
            "issueDate": issue_dt.isoformat(),
            "expiryDate": expiry.isoformat(),
            "application_id": app.id,
        }
        if company_name and not merged_data.get('companyName'):
            merged_data['companyName'] = company_name
        if company_obj and reg_no and not merged_data.get('registrationNumber'):
            merged_data['registrationNumber'] = reg_no

        # Handle specialized subtypes that require updating existing license instead of creating a new one
        handled_inline = False
        try:
            subtype_lc = (str(app.subtype or '').strip().lower())
            if subtype_lc:
                existing = License.objects.filter(owner=app.applicant, license_type=app.license_type).order_by('-created_at').first()
                if subtype_lc in ('company_grade_change', 'grade_change', 'company_grade_upgrade', 'change_grade'):
                    if not existing:
                        return response.Response({"detail": "No existing company license to change grade."}, status=status.HTTP_400_BAD_REQUEST)
                    d = existing.data if isinstance(existing.data, dict) else {}
                    # Accept new grade/category from various keys
                    ng = base_data.get('licenseType') or base_data.get('grade') or base_data.get('category') or base_data.get('newGrade')
                    if ng:
                        d['licenseType'] = ng
                        d['grade'] = ng
                    d['subtype'] = app.subtype
                    existing.data = d
                    existing.save(update_fields=['data'])
                    handled_inline = True
                elif subtype_lc in ('company_name_change', 'name_change'):
                    if not existing:
                        return response.Response({"detail": "No existing company license to change name."}, status=status.HTTP_400_BAD_REQUEST)
                    new_name = base_data.get('companyName') or base_data.get('company_name')
                    if new_name and isinstance(new_name, str):
                        try:
                            if company_obj:
                                company_obj.name = new_name.strip()
                                company_obj.save(update_fields=['name'])
                        except Exception:
                            pass
                        d = existing.data if isinstance(existing.data, dict) else {}
                        d['companyName'] = new_name.strip()
                        d['company_name'] = new_name.strip()
                        d['subtype'] = app.subtype
                        existing.data = d
                        existing.save(update_fields=['data'])
                        handled_inline = True
                elif subtype_lc in ('company_replacement', 'replacement', 'lost_replacement', 'lost_substitution'):
                    if not existing:
                        return response.Response({"detail": "No existing company license to replace."}, status=status.HTTP_400_BAD_REQUEST)
                    reason = base_data.get('replacementReason') or base_data.get('reason') or ''
                    existing.replacement_reason = reason or existing.replacement_reason
                    d = existing.data if isinstance(existing.data, dict) else {}
                    d['reissued'] = True
                    d['replacementReason'] = reason
                    d['subtype'] = app.subtype
                    existing.data = d
                    existing.save(update_fields=['replacement_reason','data'])
                    handled_inline = True
                elif subtype_lc in ('professional_upgrade', 'upgrade'):
                    if not existing:
                        return response.Response({"detail": "No existing professional license to upgrade."}, status=status.HTTP_400_BAD_REQUEST)
                    d = existing.data if isinstance(existing.data, dict) else {}
                    lvl = base_data.get('level') or base_data.get('category') or base_data.get('grade') or base_data.get('upgradeLevel')
                    if lvl:
                        d['level'] = lvl
                        d['category'] = lvl
                    d['upgraded'] = True
                    d['subtype'] = app.subtype
                    existing.data = d
                    existing.save(update_fields=['data'])
                    handled_inline = True
                elif subtype_lc in ('professional_upgrade_to_practicing', 'upgrade_to_practicing', 'to_practicing'):
                    if not existing:
                        return response.Response({"detail": "No existing professional license to upgrade to practicing."}, status=status.HTTP_400_BAD_REQUEST)
                    d = existing.data if isinstance(existing.data, dict) else {}
                    d['isPracticing'] = True
                    d['practicing'] = True
                    d['subtype'] = app.subtype
                    existing.data = d
                    existing.save(update_fields=['data'])
                    handled_inline = True
                elif subtype_lc in ('professional_replacement', 'practicing_replacement', 'practicing_lost_replacement'):
                    if not existing:
                        return response.Response({"detail": "No existing professional license to replace."}, status=status.HTTP_400_BAD_REQUEST)
                    reason = base_data.get('replacementReason') or base_data.get('reason') or ''
                    existing.replacement_reason = reason or existing.replacement_reason
                    d = existing.data if isinstance(existing.data, dict) else {}
                    d['reissued'] = True
                    d['replacementReason'] = reason
                    d['subtype'] = app.subtype
                    existing.data = d
                    existing.save(update_fields=['replacement_reason','data'])
                    handled_inline = True
        except Exception:
            handled_inline = False

        if handled_inline:
            try:
                existing_download = request.build_absolute_uri(reverse('license-download', args=[existing.id]))
                recipient = getattr(app.applicant, 'email', None)
                # Notification is now handled automatically by signals
            except Exception:
                pass
            app.approve()
            ApplicationLog.objects.create(
                application=app,
                actor=request.user,
                action="approved",
                details="Application approved and license updated"
            )
            return response.Response(self.get_serializer(app).data)

        # Prevent issuing a duplicate license of the same type for non-renewals
        if not app.is_renewal and License.objects.filter(owner=app.applicant, license_type=app.license_type).exists():
            return response.Response({"detail": "Applicant already has a license of this type."}, status=status.HTTP_400_BAD_REQUEST)

        # Persist license: for renewals, update the existing license to avoid unique constraint;
        # for new applications, create a fresh license.
        lic = None
        if app.is_renewal and getattr(app, "previous_license", None):
            lic = app.previous_license
            lic.issued_by = request.user
            lic.issued_date = issue_dt
            lic.expiry_date = expiry
            lic.data = merged_data
            lic.status = "active"
            if company_obj:
                lic.company = company_obj
            lic.save()
        else:
            lic = License.objects.create(
                owner=app.applicant,
                license_type=app.license_type,
                license_number=license_number,
                issued_by=request.user,
                issued_date=issue_dt,
                expiry_date=expiry,
                data=merged_data,
                status="active",
                company=company_obj,
            )

        # Copy application photo to license (robust across all license types)
        try:
            candidates = []
            if app.license_type == "Contractor License":
                candidates.append(app.profile_photo)
            elif app.license_type == "Professional License":
                candidates.append(app.professional_photo)
            elif app.license_type == "Import/Export License":
                candidates.append(app.company_representative_photo)
            candidates.extend([app.profile_photo, app.professional_photo, app.company_representative_photo])
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
                # Fallback: try to find an image Document attached to this application
                try:
                    docs = getattr(app, 'documents', None)
                    chosen = None
                    if docs:
                        # Prefer a document whose name indicates 'representative' photo for Import/Export license
                        if app.license_type == "Import/Export License":
                            for doc in docs.all():
                                try:
                                    nm = str(getattr(doc, 'name', '') or '').strip().lower()
                                    f = getattr(doc, 'file', None)
                                    fn = str(getattr(f, 'name', '') or '')
                                    base = fn.split('/')[-1].lower() if fn else ''
                                    if ('representative' in nm) or ('representative' in base):
                                        chosen = f
                                        break
                                except Exception:
                                    continue
                        # If not found or for other types, pick first image document
                        if not chosen:
                            for doc in docs.all():
                                f = getattr(doc, 'file', None)
                                name = getattr(f, 'name', '')
                                if isinstance(name, str) and name.lower().split('.')[-1] in ('jpg','jpeg','png','gif','webp'):
                                    chosen = f
                                    break
                    if chosen:
                        from django.core.files.base import ContentFile
                        import os
                        storage = chosen.storage
                        fh = None
                        try:
                            fh = storage.open(chosen.name, 'rb')
                            content = fh.read()
                            basename = os.path.basename(chosen.name)
                            lic.license_photo.save(basename, ContentFile(content))
                            lic.save(update_fields=['license_photo'])
                        finally:
                            try:
                                if fh: fh.close()
                            except Exception:
                                pass
                except Exception:
                    pass
            # Sync license number back to application data
            try:
                app_data = app.data if isinstance(app.data, dict) else {}
                app_data['licenseNumber'] = license_number
                app_data['license_number'] = license_number
                app.data = app_data
                app.save(update_fields=['data'])
            except Exception:
                pass
        except Exception:
            pass

        # No separate record needed for renewals due to unique constraint; license was updated in place.

        app.approve()
        ApplicationLog.objects.create(
            application=app,
            actor=request.user,
            action="approved",
            details="Application approved and license generated"
        )
        try:
            download_url = request.build_absolute_uri(reverse('license-download', args=[lic.id]))
            recipient = getattr(app.applicant, 'email', None)
            # Notification is now handled automatically by signals
        except Exception:
            pass
        return response.Response(self.get_serializer(app).data)

    @decorators.action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        app = self.get_object()
        reason = request.data.get("reason", "")
        app.reject()
        ApplicationLog.objects.create(
            application=app,
            actor=request.user,
            action="rejected",
            details=reason
        )
        # Notification is now handled automatically by signals
        return response.Response(self.get_serializer(app).data)

    @decorators.action(detail=True, methods=["post"], url_path="request_info")
    def request_info(self, request, pk=None):
        app = self.get_object()
        info_needed = request.data.get("info_needed", [])
        app.request_info()
        ApplicationLog.objects.create(
            application=app,
            actor=request.user,
            action="info_requested",
            details=f"Information requested: {', '.join(info_needed) if isinstance(info_needed, list) else str(info_needed)}"
        )
        # Notification is now handled automatically by signals
        return response.Response(self.get_serializer(app).data)

    @decorators.action(detail=True, methods=["get"], url_path="download_documents")
    def download_documents(self, request, pk=None):
        app = self.get_object()
        # Gather documents linked to the application plus any other documents uploaded by the applicant.
        # This satisfies the requirement to include "all user's documents" in the download.
        app_docs = list(app.documents.all())
        user_docs = list(Document.objects.filter(uploader=app.applicant))
        # Deduplicate by document id
        seen = set()
        documents = []
        for d in app_docs + user_docs:
            try:
                did = getattr(d, "id", None)
            except Exception:
                did = None
            if did is None or did in seen:
                continue
            seen.add(did)
            documents.append(d)

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
            for doc in documents:
                try:
                    # check if file exists
                    if doc.file and doc.file.storage.exists(doc.file.name):
                        with doc.file.storage.open(doc.file.name, "rb") as fh:
                            # Use original filename or fallback
                            base = doc.file.name.split('/')[-1]
                            safe_base = base or "document"
                            filename = (doc.name or safe_base)
                            z.writestr(filename, fh.read())
                        
                        # Log access
                        try:
                            DocumentAccessLog.objects.create(
                                user=request.user,
                                document=doc,
                                application=app,
                                action="download",
                                details="Bulk download via admin API"
                            )
                        except Exception:
                            pass
                except Exception as e:
                    # Log error but continue
                    print(f"Error zipping file {doc.id}: {e}")
                    pass
            
            # Also include application photo fields if present
            try:
                photo_fields = [
                    ("profile_photo", getattr(app, "profile_photo", None)),
                    ("professional_photo", getattr(app, "professional_photo", None)),
                    ("company_representative_photo", getattr(app, "company_representative_photo", None)),
                ]
                for label, f in photo_fields:
                    try:
                        if f and getattr(f, "name", None):
                            storage = f.storage
                            if storage and storage.exists(f.name):
                                with storage.open(f.name, "rb") as fh:
                                    base = os.path.basename(f.name)
                                    filename = base or f"{label}.jpg"
                                    z.writestr(filename, fh.read())
                    except Exception as pe:
                        print(f"Error zipping application photo {label}: {pe}")
                        continue
            except Exception:
                pass
        
        buffer.seek(0)
        filename = f"application_{app.id}_documents.zip"
        resp = HttpResponse(buffer.getvalue(), content_type="application/zip")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp

    @decorators.action(detail=True, methods=["get"], url_path="license")
    def get_license(self, request, pk=None):
        """Return the created License for this application when available.

        The endpoint will attempt to locate a License by matching the stored
        `data.application_id` or by owner+license_type as a fallback.
        """
        try:
            app = self.get_object()
            # Find license for same owner and license_type (model has no direct FK to application)
            license_qs = License.objects.filter(owner=app.applicant, license_type=app.license_type).order_by("-created_at")

            if not license_qs.exists():
                return response.Response({"detail": "No license found for this application."}, status=status.HTTP_404_NOT_FOUND)

            lic = license_qs.first()
            lic_serialized = LicenseSerializer(lic, context={"request": request}).data
            return response.Response(lic_serialized)
        except Exception as e:
            import traceback
            print(f"Error in get_license: {e}")
            print(traceback.format_exc())
            return response.Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @decorators.action(detail=True, methods=["post"], url_path="verify_documents")
    def verify_documents(self, request, pk=None):
        app = self.get_object()
        if not request.user.is_staff:
            return response.Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        
        from documents.models import Document
        from partnerships.models import Partnership, PartnershipDocument
        from vehicles.models import Vehicle

        # 1. Documents directly linked to application
        docs = list(app.documents.all())
        
        # 2. User-level documents (uploaded by applicant, not linked to any app/vehicle/partnership)
        user_docs = Document.objects.filter(
            uploader=app.applicant, 
            application__isnull=True, 
            vehicle__isnull=True
        )
        for d in user_docs:
            if d not in docs:
                docs.append(d)

        # 3. Vehicle documents for vehicles owned by applicant
        user_vehicles = Vehicle.objects.filter(owner=app.applicant)
        for v in user_vehicles:
            v_docs = Document.objects.filter(vehicle=v)
            for d in v_docs:
                if d not in docs:
                    docs.append(d)

        # 4. Partnership documents for partnerships owned by applicant
        user_partnerships = Partnership.objects.filter(owner=app.applicant)
        for p in user_partnerships:
            p_docs = PartnershipDocument.objects.filter(partnership=p)
            for pd in p_docs:
                if pd not in docs:
                    docs.append(pd)

        category = (app.license_type or "General").strip()
        res = perform_verification(docs, category)
        return response.Response(res)


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @decorators.action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return response.Response({"status": "notification marked as read"})

    @decorators.action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        self.get_queryset().update(is_read=True)
        return response.Response({"status": "all notifications marked as read"})


