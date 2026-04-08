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
        return obj.owner == request.user or request.user.is_staff or request.user.is_superuser


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
        user = self.request.user
        serializer.save(owner=user, status="pending")

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

    @decorators.action(detail=True, methods=["post"], url_path="verify_documents")
    def verify_documents(self, request, pk=None):
        try:
            partnership = self.get_object()
            if not request.user.is_staff:
                return response.Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
            
            from applications.verification import perform_verification
            docs = list(partnership.documents.all())
            if not docs:
                return response.Response({"detail": "No documents found to verify."}, status=status.HTTP_400_BAD_REQUEST)
                
            res = perform_verification(docs, "Partnership Registration")
            return response.Response(res)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            err_msg = f"Partnership Verification Error: {str(e)}"
            print(f"{err_msg}\n{tb}")
            return response.Response({
                "detail": err_msg,
                "traceback": tb if settings.DEBUG else None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST", "OPTIONS"])
@permission_classes([permissions.IsAuthenticated])
def verify_single_document(request):
    """Verify a single PartnershipDocument by its ID (Standalone View)."""
    if request.method == "OPTIONS":
        return response.Response(status=status.HTTP_200_OK)
        
    try:
        doc_id = request.data.get("document_id")
        print(f"DEBUG: verify_single_document view received doc_id='{doc_id}' (type={type(doc_id)})")
        if not doc_id:
            return response.Response({"detail": "document_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        doc = None
        # Try PartnershipDocument first
        from .models import PartnershipDocument
        from documents.models import Document
        from django.core.exceptions import ValidationError as DjangoValidationError
        
        print("DEBUG: Attempting to find PartnershipDocument...")
        try:
            # Try direct lookup (handles integer string or UUID string depending on model field)
            doc = PartnershipDocument.objects.get(id=doc_id)
            print(f"DEBUG: Found PartnershipDocument with raw ID {doc_id}")
        except (PartnershipDocument.DoesNotExist, ValueError, serializers.ValidationError, DjangoValidationError) as e:
            print(f"DEBUG: PartnershipDocument direct lookup failed: {str(e)}")
            # Try integer conversion fallback
            try:
                target_id = int(doc_id)
                doc = PartnershipDocument.objects.get(id=target_id)
                print(f"DEBUG: Found PartnershipDocument with converted integer ID {target_id}")
            except (PartnershipDocument.DoesNotExist, ValueError, TypeError, DjangoValidationError) as e2:
                print(f"DEBUG: PartnershipDocument integer fallback failed: {str(e2)}")
                pass

        if not doc:
            print("DEBUG: PartnershipDocument not found, trying generic Document...")
            # Fallback: check if it's a generic Document
            try:
                doc = Document.objects.get(id=doc_id)
                print(f"DEBUG: Found generic Document with raw ID {doc_id}")
            except (Document.DoesNotExist, ValueError, serializers.ValidationError, DjangoValidationError) as e3:
                print(f"DEBUG: Generic Document direct lookup failed: {str(e3)}")
                try:
                    target_id = int(doc_id)
                    doc = Document.objects.get(id=target_id)
                    print(f"DEBUG: Found generic Document with converted integer ID {target_id}")
                except (Document.DoesNotExist, ValueError, TypeError, DjangoValidationError) as e4:
                    print(f"DEBUG: Generic Document integer fallback failed: {str(e4)}")
                    pass

        if not doc:
            print(f"DEBUG: No document found for ID '{doc_id}' in any model.")
            return response.Response({"detail": f"Document ID {doc_id} not found in Partnership or General documents."}, status=status.HTTP_404_NOT_FOUND)

        if not request.user.is_staff:
            return response.Response({"detail": "Permission denied. Staff only."}, status=status.HTTP_403_FORBIDDEN)
        
        from applications.verification import perform_verification
        # Check if doc has a partnership or not to determine category label
        category = "Partnership Registration"
        
        # Check for PartnershipDocument
        if hasattr(doc, 'partnership') and doc.partnership:
            category = "Partnership Registration"
            print(f"DEBUG: Category determined as Partnership Registration (Partnership ID: {doc.partnership.id})")
        # Check for General Document
        elif hasattr(doc, 'application') and doc.application:
            category = getattr(doc.application, "license_type", "General")
            print(f"DEBUG: Category determined as {category} from application")
        elif hasattr(doc, 'vehicle') and doc.vehicle:
            category = "Vehicle Registration"
            print("DEBUG: Category determined as Vehicle Registration")
        
        print(f"DEBUG: Calling perform_verification for category='{category}'")
        try:
            res = perform_verification([doc], category)
            print(f"DEBUG: perform_verification success: {res}")
            return response.Response(res)
        except Exception as ai_err:
            import traceback
            tb = traceback.format_exc()
            print(f"CRITICAL: perform_verification crashed: {ai_err}\n{tb}")
            return response.Response({
                "detail": f"Verification processing error: {str(ai_err)}",
                "traceback": tb if settings.DEBUG else None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"CRITICAL: Standalone partnership document verification outer exception: {tb}")
        return response.Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
