from rest_framework import viewsets, permissions
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from .models import Document
from .serializers import DocumentSerializer
from rest_framework.decorators import action
from django.utils import timezone
import os, base64


class IsUploaderOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS or (request.user and request.user.is_staff):
            return True
        return obj.uploader == request.user


class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated, IsUploaderOrReadOnly]
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        user = self.request.user
        qs = Document.objects.all() if user.is_staff else Document.objects.filter(uploader=user)
        try:
            params = getattr(self.request, "query_params", {}) or {}
            vehicle_id = params.get("vehicle") or params.get("vehicle_id")
            if vehicle_id:
                try:
                    qs = qs.filter(vehicle_id=vehicle_id)
                except Exception:
                    pass
            app_id = params.get("application") or params.get("application_id")
            if app_id:
                try:
                    qs = qs.filter(application_id=app_id)
                except Exception:
                    pass
            uploader_id = params.get("uploader") or params.get("uploader_id")
            if uploader_id and user.is_staff:
                try:
                    qs = qs.filter(uploader_id=uploader_id)
                except Exception:
                    pass
        except Exception:
            pass
        return qs

    def perform_create(self, serializer):
        serializer.save(uploader=self.request.user)

    def create(self, request, *args, **kwargs):
        try:
            if not request.FILES.get("file") and not request.data.get("file"):
                return Response({"detail": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)
            # Normalize fields
            if request.data.get("name") and "name" not in request.data:
                request.data["name"] = request.data.get("name")
            name = (request.data.get("name") or "").strip()
            app_id = request.data.get("application") or request.data.get("application_id")
            # Upsert: if a document with same application+name already exists for this uploader, replace the file
            if app_id and name:
                try:
                    existing = Document.objects.filter(uploader=request.user, application_id=app_id, name=name).first()
                except Exception:
                    existing = None
                incoming_file = request.FILES.get("file") or request.data.get("file")
                if existing and incoming_file:
                    try:
                        # Replace file content; keep name and associations
                        existing.file = incoming_file
                        existing.uploaded_at = timezone.now()
                        existing.save(update_fields=["file", "uploaded_at"])
                    except Exception as e:
                        return Response({"detail": f"Failed to update document: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
                    ser = DocumentSerializer(existing, context={"request": request})
                    return Response(ser.data, status=status.HTTP_200_OK)
            return super().create(request, *args, **kwargs)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        try:
            # First, check if the document exists globally to distinguish between 404 and 403
            try:
                doc = Document.objects.get(pk=pk)
            except Document.DoesNotExist:
                return Response({"detail": f"Document ID {pk} not found."}, status=status.HTTP_404_NOT_FOUND)

            # Check permissions manually if get_object is failing
            if not request.user.is_staff and doc.uploader != request.user:
                return Response({"detail": "Permission denied. Only the uploader or staff can verify this document."}, status=status.HTTP_403_FORBIDDEN)
            
            from applications.verification import perform_verification
            
            # Determine category
            category = "General"
            if doc.application:
                category = (doc.application.license_type or "General").strip()
            elif doc.vehicle:
                category = "Vehicle Registration"
            
            # Use the robust verification engine
            res = perform_verification([doc], category)
            
            # Extract first result
            if res and res.get("results") and len(res["results"]) > 0:
                first = res["results"][0]
                return Response({
                    "status": first.get("status"),
                    "score": first.get("score"),
                    "details": doc.verification_details,
                })
            
            return Response({"detail": "Verification failed to produce results"}, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({"detail": f"Verification system error: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
