from rest_framework import viewsets, permissions, status, serializers, decorators, response
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.db.models import Q
from datetime import date
import re
from .models import License
from .serializers import LicenseSerializer
from applications.models import Application


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.owner == request.user


class LicenseViewSet(viewsets.ModelViewSet):
    queryset = License.objects.all().order_by("-created_at")
    serializer_class = LicenseSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def _generate_license_number(self) -> str:
        """
        Generate a unique, human-readable license number.
        Format: LIC-YYYY-XXXXXX (e.g., LIC-2026-001234)
        """
        today = date.today()
        year = today.year
        prefix = "LIC"
        seq = License.objects.count() + 1
        while True:
            candidate = f"{prefix}-{year:04d}-{seq:06d}"
            if not License.objects.filter(license_number=candidate).exists():
                return candidate
            seq += 1

    def get_queryset(self):
        user = self.request.user
        qs = License.objects.all() if user.is_staff else License.objects.filter(owner=user)
        # Auto-mark expired licenses
        try:
            today = date.today()
            to_expire = qs.filter(expiry_date__lte=today, status__in=('active','approved'))
            if to_expire.exists():
                to_expire.update(status='expired')
        except Exception:
            pass
        return qs

    def perform_create(self, serializer):
        """
        When a license is created via the API, ensure it always
        has a unique license_number and sensible validity dates
        so that it can be verified by number.
        """
        today = date.today()
        # Default to 5‑year validity window
        expiry = date(today.year + 5, today.month, today.day)

        # Preserve any existing data while injecting standard fields
        existing_data = serializer.validated_data.get("data") or {}
        if not isinstance(existing_data, dict):
            existing_data = {}

        # Prevent creating a duplicate license of the same type for the same owner
        requested_type = serializer.validated_data.get('license_type')
        if License.objects.filter(owner=self.request.user, license_type=requested_type).exists():
            raise serializers.ValidationError({
                'license_type': 'You already have a license of this type.'
            })

        # Generate a unique public license number
        license_number = self._generate_license_number()

        merged_data = {
            **existing_data,
            "licenseNumber": license_number,
            "issueDate": today.isoformat(),
            "expiryDate": expiry.isoformat(),
        }

        serializer.save(
            owner=self.request.user,
            license_number=license_number,
            issued_date=today,
            expiry_date=expiry,
            status="active",
            data=merged_data,
        )

    def perform_update(self, serializer):
        """
        Prevent changing a license such that a user would end up with two licenses
        of the same license_type.
        """
        # Determine the target license_type (either updated value or existing)
        new_type = serializer.validated_data.get('license_type', None)
        instance = getattr(serializer, 'instance', None)
        if instance is None:
            return serializer.save()

        target_type = new_type or instance.license_type
        # If the type is changing (or set to same), ensure no other license with that
        # owner+type exists (excluding this instance)
        conflict_qs = License.objects.filter(owner=instance.owner, license_type=target_type).exclude(pk=instance.pk)
        if conflict_qs.exists():
            raise serializers.ValidationError({
                'license_type': 'This change would result in a duplicate license of the same type for this user.'
            })

        serializer.save()

    @decorators.action(detail=True, methods=["post"], url_path="renew")
    def renew(self, request, pk=None):
        lic = self.get_object()
        user = request.user
        # Create a renewal application linked to previous license, pre-filling data
        from applications.models import Application
        # Allow renewals even if user already has a license of same type
        base_data = lic.data if isinstance(lic.data, dict) else {}
        renew_data = {
            **base_data,
            "renewal": {
                "fromLicenseId": lic.id,
                "fromLicenseNumber": lic.license_number or base_data.get("licenseNumber"),
            }
        }
        # Merge incoming data (e.g., payment info or docs)
        try:
            if isinstance(request.data, dict):
                rd = request.data.get("data") or {}
                if isinstance(rd, dict):
                    renew_data.update(rd)
        except Exception:
            pass
        app = Application.objects.create(
            applicant=user,
            license_type=lic.license_type,
            data=renew_data,
            is_renewal=True,
            previous_license=lic,
            subtype=base_data.get("subtype"),
        )
        # Return renewal application payload for frontend to continue uploads/payment
        from applications.serializers import ApplicationSerializer
        return response.Response(ApplicationSerializer(app, context={"request": request}).data, status=status.HTTP_201_CREATED)


class LicenseVerificationSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    license_number = serializers.CharField(read_only=True)
    license_type = serializers.CharField(read_only=True)
    holder_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    company_name = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    issued_date = serializers.DateField(read_only=True)
    expiry_date = serializers.DateField(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)
    qr_code_data = serializers.CharField(read_only=True)
    authorized_scope = serializers.SerializerMethodField()
    subtype = serializers.SerializerMethodField()
    license_photo_url = serializers.SerializerMethodField()

    def get_authorized_scope(self, obj):
        """Extract authorized scope from license data"""
        if obj.data and isinstance(obj.data, dict):
            # Check for various possible field names
            scope = obj.data.get('authorized_scope') or obj.data.get('authorizedScope') or obj.data.get('scope')
            if scope:
                # If it's a list, join it with commas
                if isinstance(scope, list):
                    return ', '.join(str(s).title() for s in scope)
                return str(scope)
            
            # Check for workScopes array (common in contractor applications)
            work_scopes = obj.data.get('workScopes') or obj.data.get('work_scopes')
            if work_scopes and isinstance(work_scopes, list):
                # Format work scopes nicely (e.g., "Building Construction, Road Construction")
                formatted_scopes = []
                for ws in work_scopes:
                    ws_str = str(ws).replace('_', ' ').title()
                    # Add "Construction" suffix if not already present for common types
                    if ws_str.lower() in ['building', 'road', 'bridge', 'electrical', 'plumbing']:
                        ws_str = f"{ws_str} Construction"
                    formatted_scopes.append(ws_str)
                return ', '.join(formatted_scopes)
            
            # If no explicit scope, derive from license type and subtype
            subtype = obj.data.get('subtype')
            if subtype:
                subtype_display = str(subtype).replace('-', ' ').replace('_', ' ').title()
                return f"{obj.get_license_type_display()} - {subtype_display}"
        
        # Fallback: check if subtype exists on the model itself
        subtype = getattr(obj, 'subtype', None)
        if subtype:
            subtype_display = str(subtype).replace('-', ' ').replace('_', ' ').title()
            return f"{obj.get_license_type_display()} - {subtype_display}"
        
        # Final fallback to license type display
        return obj.get_license_type_display()

    def get_subtype(self, obj):
        """Extract subtype from license data"""
        if obj.data and isinstance(obj.data, dict):
            return obj.data.get('subtype')
        return None
    
    def get_license_photo_url(self, obj):
        request = self.context.get('request') if isinstance(self.context, dict) else None
        if getattr(obj, 'license_photo', None):
            try:
                url = obj.license_photo.url
                if request:
                    return request.build_absolute_uri(url)
                return url
            except Exception:
                return None
        return None

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # A license is valid if it's approved or active (and not expired)
        is_approved_or_active = instance.status in ('approved', 'active')
        is_not_expired = not instance.expiry_date or instance.expiry_date >= date.today()
        representation['is_valid'] = is_approved_or_active and is_not_expired
        
        # Ensure license_number is always returned (even if None in DB, use the instance value)
        if not representation.get('license_number') and instance.license_number:
            representation['license_number'] = instance.license_number
        
        # Format license type with subtype if available (e.g., "Contractor License - Grade A")
        subtype = representation.get('subtype')
        if subtype and representation.get('license_type'):
            license_type_display = instance.get_license_type_display()
            subtype_str = str(subtype).replace('-', ' ').replace('_', ' ').strip()
            # Format as "Contractor License - Grade A" style
            if 'grade' in subtype_str.lower() or len(subtype_str.split()) == 1:
                # Single word or contains "grade" - treat as grade
                grade_part = subtype_str.split()[-1].upper() if subtype_str.split() else subtype_str.upper()
                representation['license_type'] = f"{license_type_display} - Grade {grade_part}"
            else:
                # Multi-word subtype
                subtype_display = ' '.join(word.capitalize() for word in subtype_str.split())
                representation['license_type'] = f"{license_type_display} - {subtype_display}"
        
        # Handle holder_name - prioritize company name, then user full name, then email/username
        holder_name = representation.get('holder_name')
        # Include company_name explicitly from license data if available
        try:
            if instance.data and isinstance(instance.data, dict):
                company_name = instance.data.get('company_name') or instance.data.get('companyName')
                if company_name and str(company_name).strip():
                    representation['company_name'] = str(company_name).strip()
        except Exception:
            pass

from rest_framework.views import APIView

class LicenseRenewalsList(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        from applications.models import Application
        from applications.serializers import ApplicationSerializer
        user = request.user
        qs = Application.objects.filter(is_renewal=True)
        if not user.is_staff:
            qs = qs.filter(applicant=user)
        data = ApplicationSerializer(qs, many=True, context={"request": request}).data
        return Response(data)

class LicenseRenewalApproveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk, *args, **kwargs):
        # Delegate to ApplicationViewSet.approve
        from applications.models import Application
        from applications.views import ApplicationViewSet
        app = get_object_or_404(Application, pk=pk, is_renewal=True)
        viewset = ApplicationViewSet()
        viewset.request = request
        viewset.kwargs = {"pk": pk}
        return viewset.approve(request, pk)

class LicenseRenewalRejectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk, *args, **kwargs):
        from applications.models import Application
        from applications.views import ApplicationViewSet
        app = get_object_or_404(Application, pk=pk, is_renewal=True)
        viewset = ApplicationViewSet()
        viewset.request = request
        viewset.kwargs = {"pk": pk}
        return viewset.reject(request, pk)
        if not holder_name or holder_name == '' or holder_name == 'None':
            # Try to get company name from data first
            if instance.data and isinstance(instance.data, dict):
                company_name = instance.data.get('company_name') or instance.data.get('companyName')
                if company_name and company_name.strip():
                    representation['holder_name'] = company_name.strip()
                else:
                    # Fallback to user's full name or email/username
                    owner = instance.owner
                    if owner:
                        full_name = getattr(owner, 'get_full_name', lambda: '')()
                        if full_name and full_name.strip():
                            representation['holder_name'] = full_name.strip()
                        else:
                            representation['holder_name'] = getattr(owner, 'email', getattr(owner, 'username', 'N/A'))
            else:
                # No data field, use owner info
                owner = instance.owner
                if owner:
                    full_name = getattr(owner, 'get_full_name', lambda: '')()
                    if full_name and full_name.strip():
                        representation['holder_name'] = full_name.strip()
                    else:
                        representation['holder_name'] = getattr(owner, 'email', getattr(owner, 'username', 'N/A'))
        
        # Format dates as strings in YYYY-MM-DD format
        if representation.get('issued_date'):
            if isinstance(representation['issued_date'], date):
                representation['issued_date'] = representation['issued_date'].isoformat()
        if representation.get('expiry_date'):
            if isinstance(representation['expiry_date'], date):
                representation['expiry_date'] = representation['expiry_date'].isoformat()
        
        return representation


class LicenseQRGenerationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        license_id = request.data.get('license_id')
        frontend_url = request.data.get('frontend_url', 'http://localhost:3000')
        # Use TimestampSigner to create a signed token that expires
        signer = TimestampSigner()

        if not license_id:
            return Response({"detail": "License ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        license = get_object_or_404(License, id=license_id, owner=request.user)

        token = signer.sign(str(license.id))
        verification_url = f"{frontend_url}/verify?token={token}"

        # save the signed verification url (or token) to the license for convenience
        license.qr_code_data = verification_url
        license.save()

        return Response(
            {
                "success": True,
                "license_id": str(license.id),
                "qr_code_data": license.qr_code_data,
                "message": "QR code data generated and saved."
            },
            status=status.HTTP_200_OK
        )


class LicenseVerificationView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        token = request.query_params.get('token')
        license = None
        # Accept both camelCase and snake_case for license number
        license_number = request.query_params.get('licenseNumber') or request.query_params.get('license_number')

        # prefer token if provided
        if token:
            signer = TimestampSigner()
            max_age = getattr(settings, 'QR_TOKEN_MAX_AGE_SECONDS', 60 * 60 * 24 * 365)  # default 1 year
            try:
                # unsign will raise SignatureExpired or BadSignature
                unsigned = signer.unsign(token, max_age=max_age)
                unsigned_str = str(unsigned).strip()
                if re.match(r'^\d+$', unsigned_str):
                    try:
                        lcid = int(unsigned_str)
                        license = License.objects.filter(id=lcid).first()
                        if license:
                            # We already have the license; skip number-based search
                            license_number = license.license_number or unsigned_str
                        else:
                            license_number = unsigned_str
                    except Exception:
                        license_number = unsigned_str
                else:
                    license_number = unsigned_str
            except SignatureExpired:
                return Response({"valid": False, "detail": "Token expired."}, status=status.HTTP_400_BAD_REQUEST)
            except BadSignature:
                return Response({"valid": False, "detail": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)

        if not (license_number or 'license' in locals()):
            return Response({"valid": False, "detail": "License number or token is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Strip whitespace and normalize the license number
        license_number = str(license_number).strip()
        if not license_number:
            return Response({"valid": False, "detail": "License number cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)

        # Normalize old CL- format to LIC- format for search (for backward compatibility)
        search_number = license_number
        cl_pattern = re.compile(r'^CL-(\d{4})-(\d{6})$', re.IGNORECASE)
        cl_match = cl_pattern.match(license_number)
        if cl_match:
            year = cl_match.group(1)
            seq = cl_match.group(2)
            search_number = f'LIC-{year}-{seq}'

        try:
            if 'license' in locals() and license:
                license = license
            else:
                license = (
                    License.objects.filter(Q(license_number__iexact=license_number) | Q(license_number__iexact=search_number))
                    .first()
                )

            if not license:
                candidates = []
                try:
                    s = str(license_number)
                    candidates = [s, s.upper(), s.lower()]
                except Exception:
                    candidates = []
                for candidate in candidates:
                    license = (
                        License.objects.filter(Q(data__licenseNumber=candidate) | Q(data__license_number=candidate) | Q(data__registrationNumber=candidate) | Q(data__registration_number=candidate))
                        .first()
                    )
                    if license:
                        if not license.license_number or license.license_number.strip() == '':
                            canonical = None
                            if license.data and isinstance(license.data, dict):
                                canonical = license.data.get('licenseNumber') or license.data.get('license_number') or license.data.get('registrationNumber') or license.data.get('registration_number')
                            normalized = (canonical or candidates[0] or '').strip() if candidates else ''
                            if normalized:
                                license.license_number = normalized
                                license.save(update_fields=['license_number'])
                        break

            if not license:
                try:
                    app = Application.objects.filter(Q(data__licenseNumber=license_number) | Q(data__license_number=license_number)).first()
                    if app:
                        lic = License.objects.filter(owner=app.applicant, license_type=app.license_type).order_by('-created_at').first()
                        if lic:
                            license = lic
                            if not license.license_number or license.license_number.strip() == '':
                                if not license.data or not isinstance(license.data, dict):
                                    license.data = {}
                                ln = str(license_number or '').strip()
                                license.license_number = ln
                                license.data['licenseNumber'] = ln
                                license.data['license_number'] = ln
                                if ln:
                                    license.save(update_fields=['license_number', 'data'])
                except Exception:
                    pass

            if not license:
                try:
                    s = str(license_number).strip()
                    # Normalize unicode dashes to hyphen-minus
                    dash_chars = r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFE58\uFE63\uFF0D]"
                    s = re.sub(dash_chars, "-", s)
                    license = (
                        License.objects.filter(
                            Q(license_number__icontains=s)
                            | Q(data__licenseNumber__icontains=s)
                            | Q(data__license_number__icontains=s)
                            | Q(data__registrationNumber__icontains=s)
                            | Q(data__registration_number__icontains=s)
                        )
                    ).first()
                    if license and (not license.license_number or license.license_number.strip() == ''):
                        try:
                            c = None
                            if isinstance(license.data, dict):
                                c = license.data.get('licenseNumber') or license.data.get('license_number') or license.data.get('registrationNumber') or license.data.get('registration_number')
                            normalized = (c or s).strip()
                            if normalized:
                                license.license_number = normalized
                                license.save(update_fields=['license_number'])
                        except Exception:
                            pass
                except Exception:
                    pass
            
            # Last-chance robust match: compare normalized forms across recent active/approved licenses
            if not license:
                try:
                    def normalize(v):
                        try:
                            t = str(v or '').strip()
                            t = re.sub(dash_chars, "-", t)
                            return t.replace(" ", "").upper()
                        except Exception:
                            return ""
                    target_norm = normalize(license_number)
                    candidates = (
                        License.objects.filter(Q(status__in=['active','approved']))
                        .order_by('-created_at')[:200]
                    )
                    for cand in candidates:
                        cvals = [
                            getattr(cand, 'license_number', None),
                        ]
                        d = getattr(cand, 'data', None)
                        if isinstance(d, dict):
                            cvals.extend([
                                d.get('licenseNumber'),
                                d.get('license_number'),
                                d.get('registrationNumber'),
                                d.get('registration_number'),
                            ])
                        if any(normalize(v) == target_norm for v in cvals):
                            license = cand
                            # backfill standardized column if missing
                            if not cand.license_number:
                                pick = next((v for v in cvals if normalize(v) == target_norm and v), None)
                                if pick:
                                    cand.license_number = str(pick).strip()
                                    try:
                                        cand.save(update_fields=['license_number'])
                                    except Exception:
                                        pass
                            break
                except Exception:
                    pass

            # 3) Auto-migrate old formats (CL-YYYY-NNNNNN or LIC-X) to LIC-YYYY-NNNNNN format if found
            if license and license.license_number:
                old_number = license.license_number
                new_number = None
                
                # Check for CL-YYYY-NNNNNN format
                if old_number.startswith('CL-'):
                    cl_pattern = re.compile(r'^CL-(\d{4})-(\d{6})$', re.IGNORECASE)
                    match = cl_pattern.match(old_number)
                    if match:
                        year = match.group(1)
                        seq = match.group(2)
                        new_number = f'LIC-{year}-{seq}'
                
                # Check for LIC-X simple format (LIC-5, LIC-123, etc.)
                elif old_number.startswith('LIC-') and not re.match(r'^LIC-\d{4}-\d{6}$', old_number):
                    lic_simple_pattern = re.compile(r'^LIC-(\d+)$', re.IGNORECASE)
                    match = lic_simple_pattern.match(old_number)
                    if match:
                        seq_num = int(match.group(1))
                        # Use issued_date year if available, otherwise current year
                        if license.issued_date:
                            year = str(license.issued_date.year)
                        else:
                            year = str(date.today().year)
                        # Pad sequence to 6 digits
                        seq = f'{seq_num:06d}'
                        new_number = f'LIC-{year}-{seq}'
                
                # Migrate if new format found and doesn't already exist
                if new_number and not License.objects.filter(license_number=new_number).exclude(id=license.id).exists():
                    license.license_number = new_number
                    # Also update in data field if present
                    if license.data and isinstance(license.data, dict):
                        if 'licenseNumber' in license.data:
                            license.data['licenseNumber'] = new_number
                        if 'license_number' in license.data:
                            license.data['license_number'] = new_number
                    license.save(update_fields=['license_number', 'data'])
                    # Log the migration (optional - can be removed in production)
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f'Auto-migrated license {license.id}: {old_number} → {new_number}')

            if not license:
                return Response(
                    {"valid": False, "detail": "The license number you entered was not found in the database."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            # Check if license is approved or active (these are verifiable)
            # Only licenses with status 'approved' or 'active' can be verified
            if license.status not in ('approved', 'active'):
                serializer = LicenseVerificationSerializer(license, context={"request": request})
                response_data = serializer.data
                response_data["valid"] = False
                response_data["detail"] = f"This license exists but is not approved. Current status: {license.get_status_display()}."
                return Response(response_data, status=status.HTTP_200_OK)
            
            # Check if license is expired
            if license.expiry_date and license.expiry_date < date.today():
                serializer = LicenseVerificationSerializer(license, context={"request": request})
                response_data = serializer.data
                response_data['valid'] = False
                response_data['detail'] = f"This license has expired on {license.expiry_date}."
                return Response(response_data, status=status.HTTP_200_OK)
            
            # License is valid (approved/active and not expired) - return full details
            serializer = LicenseVerificationSerializer(license, context={"request": request})
            response_data = serializer.data
            response_data['valid'] = True
            return Response(response_data, status=status.HTTP_200_OK)
            
        except License.DoesNotExist:
            return Response({"valid": False, "detail": "The license number you entered was not found in the database."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            msg = str(e)
            if 'not iterable' in msg.lower():
                return Response({"valid": False, "detail": "The license number you entered was not found in the database."}, status=status.HTTP_404_NOT_FOUND)
            return Response({"valid": False, "detail": f"An error occurred: {msg}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LicenseDownloadView(APIView):
    """
    Provide license data for download only if the license was approved/issued by an approver.
    Returns 403 with a clear message when approval is required.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        try:
            license = get_object_or_404(License, pk=pk)

            # Only owner or staff can download
            if not (request.user == license.owner or request.user.is_staff):
                return Response({"detail": "Not permitted."}, status=status.HTTP_403_FORBIDDEN)

            # Require status to reflect approval or active; issued_by is optional for derived/self-issued licenses
            if license.status not in ("approved", "active"):
                return Response({"detail": "Approval required first approved by approver"}, status=status.HTTP_403_FORBIDDEN)

            serializer = LicenseSerializer(license, context={"request": request})
            return Response({"success": True, "license": serializer.data}, status=status.HTTP_200_OK)

        except License.DoesNotExist:
            return Response({"detail": "License not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"detail": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
