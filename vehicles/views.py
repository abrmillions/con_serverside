from rest_framework import viewsets, permissions, serializers, decorators, response, status
from django.conf import settings
from .models import Vehicle
from .serializers import VehicleSerializer
from applications.verification import perform_verification


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.owner == request.user or request.user.is_staff


class VehicleViewSet(viewsets.ModelViewSet):
    serializer_class = VehicleSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Vehicle.objects.all()
        return Vehicle.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        user = self.request.user
        try:
            serializer.save(owner=user)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(tb)
            raise serializers.ValidationError({
                "detail": str(e),
                "traceback": tb if settings.DEBUG else None
            })

    @decorators.action(detail=True, methods=["post"], url_path="verify_documents")
    def verify_documents(self, request, pk=None):
        try:
            vehicle = self.get_object()
            if not request.user.is_staff:
                return response.Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
            
            docs = list(vehicle.documents.all())
            res = perform_verification(docs, "Vehicle Registration")
            return response.Response(res)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Vehicle verification error: {tb}")
            return response.Response({
                "detail": f"An error occurred: {str(e)}",
                "traceback": tb if settings.DEBUG else None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@decorators.api_view(["POST"])
@decorators.permission_classes([permissions.IsAdminUser])
def verify_single_vehicle_document(request):
    print("DEBUG: verify_single_vehicle_document view started")
    try:
        doc_id = request.data.get("document_id")
        print(f"DEBUG: Received document_id: {doc_id}")
        if not doc_id:
            print("DEBUG: document_id is missing")
            return response.Response({"detail": "document_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        from documents.models import Document
        try:
            print(f"DEBUG: Querying for Document with id={doc_id}")
            doc = Document.objects.get(id=doc_id)
            print(f"DEBUG: Found document: {doc}")
        except (Document.DoesNotExist, ValueError) as e:
            print(f"DEBUG: Document not found. Error: {e}")
            return response.Response({"detail": "Document not found."}, status=status.HTTP_404_NOT_FOUND)
            
        # Ensure it's a vehicle document
        if not doc.vehicle:
             print(f"DEBUG: Document {doc_id} is not a vehicle document.")
             return response.Response({"detail": "Document is not associated with a vehicle."}, status=status.HTTP_400_BAD_REQUEST)

        print(f"DEBUG: Calling perform_verification for doc {doc_id}")
        res = perform_verification([doc], "Vehicle Registration")
        print(f"DEBUG: perform_verification returned: {res}")
        return response.Response(res)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"CRITICAL: Single vehicle document verification error: {tb}")
        return response.Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
