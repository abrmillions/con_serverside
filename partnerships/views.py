from rest_framework import viewsets, permissions, decorators, response, status, serializers
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from django.conf import settings
from django.core.files.base import ContentFile
import io, json
import qrcode
from .models import Partnership, PartnershipApprovalLog
from .serializers import PartnershipSerializer
from datetime import datetime


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.owner == request.user


def validate_partnership_rules(partnership: Partnership):
    # Foreign ownership limit: if foreign-local, partner share must be <= 49
    if partnership.is_foreign and float(partnership.ownership_ratio_partner) > 49.0:
        return False, "Foreign ownership exceeds limit (<= 49%)"
    # Both companies must have valid licenses and be active
    if not partnership.main_contractor.license_valid():
        return False, "Main contractor license invalid or company suspended"
    if not partnership.partner_company.license_valid():
        return False, "Partner company license invalid or company suspended"
    # Blacklist check: explicit suspension on partner
    if partnership.partner_company.status == "suspended":
        return False, "Partner blacklisted"
    # Duplicate prevention: same companies with overlapping active dates
    dup = Partnership.objects.filter(
        main_contractor=partnership.main_contractor,
        partner_company=partnership.partner_company,
        status__in=["pending", "awaiting_partner_approval", "awaiting_government_review", "approved", "active"],
    ).exclude(id=partnership.id).exists()
    if dup:
        return False, "Duplicate partnership exists for these companies"
    return True, "OK"


def generate_qr_png(partnership: Partnership):
    payload = {
        "partnership_id": str(partnership.id),
        "companies": [partnership.main_contractor.name, partnership.partner_company.name],
        "validity_period": {
            "start": str(partnership.start_date) if partnership.start_date else None,
            "end": str(partnership.end_date) if partnership.end_date else None,
        },
    }
    img = qrcode.make(json.dumps(payload))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    partnership.qr_code.save(f"partnership_{partnership.id}.png", ContentFile(buf.read()))


class PartnershipViewSet(viewsets.ModelViewSet):
    """
    Partnerships API

    - Non-staff users only see their own partnerships.
    - Staff/superusers can see all partnerships.
    """

    queryset = Partnership.objects.all()
    serializer_class = PartnershipSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Partnership.objects.all()
        return Partnership.objects.filter(owner=user)

    def perform_create(self, serializer):
        # Enforce: one partnership per user account (email)
        user = self.request.user
        if Partnership.objects.filter(owner=user).exists():
            raise serializers.ValidationError({"detail": "You have already registered a partnership with this account."})
        serializer.save(owner=user, status="pending")

    @decorators.action(detail=False, methods=["post"], url_path="create")
    def create_request(self, request):
        """Contractor creates partnership"""
        # Enforce: one partnership per user account (email)
        if Partnership.objects.filter(owner=request.user).exists():
            return response.Response({"detail": "You have already registered a partnership with this account."}, status=status.HTTP_400_BAD_REQUEST)
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        partnership = ser.save(owner=request.user, status="pending")
        return response.Response(self.get_serializer(partnership).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        """Partner accepts or rejects"""
        obj = self.get_object()
        action = str(request.data.get("action", "")).lower()
        if action == "accept":
            obj.status = "awaiting_government_review"
            act = "partner_accepted"
        else:
            obj.status = "rejected"
            act = "partner_rejected"
        obj.save(update_fields=["status"])
        return response.Response(self.get_serializer(obj).data)

    @decorators.action(detail=False, methods=["get"], url_path="pending")
    def pending(self, request):
        """Government dashboard list"""
        if not request.user.is_staff and not request.user.is_superuser:
            return response.Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        qs = Partnership.objects.filter(status__in=["pending", "awaiting_partner_approval", "awaiting_government_review"])
        ser = self.get_serializer(qs, many=True)
        return response.Response(ser.data)

    @decorators.action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        """Government approval"""
        obj = self.get_object()
        if not request.user.is_staff and not request.user.is_superuser:
            return response.Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        ok, msg = validate_partnership_rules(obj)
        if not ok:
            return response.Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)
        obj.status = "approved"
        # Generate certificate number if missing, format: CP-YYYY-XXXXXX
        try:
            if not obj.certificate_number:
                from django.utils import timezone
                try:
                    yr = (obj.start_date or obj.created_at or timezone.now()).year
                except Exception:
                    yr = timezone.now().year
                raw = "".join(str(obj.id).split("-"))
                last6 = (raw[-6:] if raw else "").lower()
                obj.certificate_number = f"CP-{yr}-{last6}"
        except Exception:
            # keep silent if generation fails; verification by UUID still works
            pass
        obj.save(update_fields=["status", "certificate_number"])
        generate_qr_png(obj)
        return response.Response(self.get_serializer(obj).data)

    @decorators.action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        obj = self.get_object()
        if not request.user.is_staff and not request.user.is_superuser:
            return response.Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        obj.status = "rejected"
        obj.save(update_fields=["status"])
        return response.Response(self.get_serializer(obj).data)

    @decorators.action(detail=False, methods=["get"], url_path="active")
    def active(self, request):
        qs = Partnership.objects.filter(status__in=["approved", "active"]).exclude(status="expired")
        ser = self.get_serializer(qs, many=True)
        return response.Response(ser.data)

    @decorators.action(detail=True, methods=["post"], url_path="upload_document")
    def upload_document(self, request, pk=None):
        """Upload partnership legal document (PDF/image)."""
        obj = self.get_object()
        # allow owner, staff, and partner's owner
        user = request.user
        allowed = user.is_staff or user.is_superuser or obj.owner_id == user.id or (obj.partner_company and obj.partner_company.owner_id == user.id)
        if not allowed:
            return response.Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        file = request.FILES.get("file")
        doc_type = request.data.get("document_type") or "General"
        if not file:
            return response.Response({"detail": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)
        from .models import PartnershipDocument
        PartnershipDocument.objects.create(partnership=obj, document_type=str(doc_type), file=file)
        return response.Response({"detail": "Uploaded"}, status=status.HTTP_201_CREATED)


class PartnershipPublicView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, id):
        try:
            obj = Partnership.objects.get(id=id)
        except Partnership.DoesNotExist:
            return response.Response({"valid": False, "detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        main_name = obj.main_contractor.name
        partner_name = obj.partner_company.name
        main_license = getattr(obj.main_contractor, "license_number", None)
        partner_license = getattr(obj.partner_company, "license_number", None)
        data = {
            "valid": obj.status in ["approved", "active"] and obj.status != "expired",
            "id": str(obj.id),
            "main_contractor": main_name,
            "partner_company": partner_name,
            "main_license_number": main_license,
            "partner_license_number": partner_license,
            "status": obj.status,
            "start_date": obj.start_date,
            "end_date": obj.end_date,
        }
        return response.Response(data)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def verify_partnership(request, id):
    try:
        p = Partnership.objects.get(id=id)
    except Partnership.DoesNotExist:
        return response.Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    main_name = p.main_contractor.name
    partner_name = p.partner_company.name
    return response.Response({
        "main_company": main_name,
        "partner_company": partner_name,
        "ownership_partner": float(p.ownership_ratio_partner),
        "valid_until": p.end_date,
        "status": p.status,
    })

@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def verify_partnership_by_cert(request, cert):
    target = str(cert or "").strip().upper()
    p = Partnership.objects.filter(certificate_number__iexact=target).first()
    if not p:
        return response.Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    return response.Response({
        "main_company": p.main_contractor.name,
        "partner_company": p.partner_company.name,
        "ownership_partner": float(p.ownership_ratio_partner),
        "valid_until": p.end_date,
        "status": p.status,
        "id": str(p.id),
        "valid": p.status in ["approved", "active"] and p.status != "expired",
    })
