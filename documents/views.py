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
        if request.method in permissions.SAFE_METHODS:
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
            if request.data.get("name") and "name" not in request.data:
                request.data["name"] = request.data.get("name")
            return super().create(request, *args, **kwargs)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        try:
            doc = self.get_object()
        except Exception:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            f = getattr(doc, "file", None)
            if not f:
                return Response({"detail": "No file"}, status=status.HTTP_400_BAD_REQUEST)
            storage = f.storage
            if not storage.exists(f.name):
                return Response({"detail": "Missing file"}, status=status.HTTP_404_NOT_FOUND)
            ext = ""
            try:
                ext = os.path.splitext(f.name)[1].lower().strip(".")
            except Exception:
                ext = ""
            b64 = None
            if ext in ("jpg","jpeg","png","gif","webp"):
                try:
                    fh = storage.open(f.name, "rb")
                    content = fh.read()
                finally:
                    try:
                        fh.close()
                    except Exception:
                        pass
                b64 = base64.b64encode(content).decode("ascii")
            elif ext == "pdf":
                try:
                    import fitz
                    fh = storage.open(f.name, "rb")
                    try:
                        content = fh.read()
                    finally:
                        try:
                            fh.close()
                        except Exception:
                            pass
                    doc_pdf = fitz.open(stream=content, filetype="pdf")
                    page = doc_pdf.load_page(0)
                    pix = page.get_pixmap()
                    png_bytes = pix.tobytes("png")
                    b64 = base64.b64encode(png_bytes).decode("ascii")
                except Exception:
                    b64 = None
            if b64 is not None:
                score = None
                status_label = "inconclusive"
                details = ""
                try:
                    from openai import OpenAI
                    api_key = os.environ.get("OPENAI_API_KEY")
                    if api_key:
                        client = OpenAI(api_key=api_key)
                        msg = [
                            {"role": "system", "content": "You assess whether an Ethiopian license application document image is likely authentic or tampered. Consider layout conformity, official stamps/seals, dates, IDs, and editing artifacts. Return a likelihood between 0 and 1 and a short reason."},
                            {"role": "user", "content": [{"type":"input_text","text":"Analyze authenticity and return score and reason."},{"type":"input_image","image_data":b64}]},
                        ]
                        r = client.chat.completions.create(model="gpt-4.1-mini", messages=msg)
                        txt = r.choices[0].message.content or ""
                        s = None
                        try:
                            import re
                            m = re.search(r'([01](?:\.\d+)?)', txt)
                            if m:
                                s = float(m.group(1))
                        except Exception:
                            s = None
                        score = s if s is not None else None
                        details = txt
                        if score is not None:
                            true_t = 0.7
                            fake_t = 0.3
                            try:
                                from django.conf import settings
                                model_path = os.path.join(settings.MEDIA_ROOT, "datasets", "contractor", "model.json")
                                if os.path.exists(model_path):
                                    import json
                                    with open(model_path, "r", encoding="utf-8") as mf:
                                        cfg = json.load(mf)
                                    tt = cfg.get("true_threshold")
                                    if isinstance(tt, (int,float)):
                                        true_t = float(tt)
                            except Exception:
                                pass
                            status_label = "verified_true" if score >= true_t else ("verified_fake" if score <= fake_t else "inconclusive")
                except Exception:
                    score = None
                    details = ""
                    status_label = "inconclusive"
                doc.verification_status = status_label
                doc.verification_score = score
                doc.verification_details = details
                doc.verified_at = timezone.now()
                doc.save(update_fields=["verification_status","verification_score","verification_details","verified_at"])
                return Response({"status": status_label, "score": score, "details": details})
            else:
                doc.verification_status = "inconclusive"
                doc.verification_score = None
                doc.verification_details = ""
                doc.verified_at = timezone.now()
                doc.save(update_fields=["verification_status","verification_score","verification_details","verified_at"])
                return Response({"status": "inconclusive"})
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
