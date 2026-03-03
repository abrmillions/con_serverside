from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .models import ContactMessage, ContactReply
from .serializers import ContactMessageSerializer, ContactReplySerializer
from django.core.mail import EmailMultiAlternatives, get_connection
from systemsettings.models import SystemSettings
import logging

logger = logging.getLogger(__name__)


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def messages_view(request):
    if request.method == "POST":
        name = request.data.get("name") or ""
        email = request.data.get("email") or ""
        subject = request.data.get("subject") or ""
        message_text = request.data.get("message") or ""
        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        obj = ContactMessage.objects.create(user=user, name=name, email=email, subject=subject, message=message_text, status="open")
        ser = ContactMessageSerializer(obj)
        return Response(ser.data, status=status.HTTP_201_CREATED)
    if not getattr(request, "user", None) or not request.user.is_staff:
        return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    qs = ContactMessage.objects.order_by("-created_at")
    ser = ContactMessageSerializer(qs, many=True)
    return Response(ser.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def message_detail_view(request, pk: int):
    msg = ContactMessage.objects.filter(id=pk).first()
    if not msg:
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "GET":
        if not getattr(request, "user", None) or not request.user.is_staff:
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
        ser = ContactMessageSerializer(msg)
        return Response(ser.data)


@api_view(["POST"])
@permission_classes([AllowAny])
def reply_view(request, pk: int):
    msg = ContactMessage.objects.filter(id=pk).first()
    if not msg:
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    if not getattr(request, "user", None) or not request.user.is_staff:
        return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    text = request.data.get("text") or request.data.get("message") or ""
    if not text.strip():
        return Response({"detail": "Reply text required"}, status=status.HTTP_400_BAD_REQUEST)
    rep = ContactReply.objects.create(message=msg, sender=request.user, sender_type="admin", text=text.strip())
    ser = ContactReplySerializer(rep)
    msg.status = "open"
    msg.save(update_fields=["status"])

    try:
        settings_obj = SystemSettings.get_solo()
        if getattr(settings_obj, "email_notifications", True):
            host = getattr(settings_obj, "smtp_host", "") or ""
            port = int(getattr(settings_obj, "smtp_port", 587) or 587)
            user = getattr(settings_obj, "smtp_user", "") or ""
            password = getattr(settings_obj, "smtp_password", "") or ""
            use_tls = bool(getattr(settings_obj, "use_tls", True))
            if host and user:
                connection = get_connection(
                    host=host,
                    port=port,
                    username=user,
                    password=password,
                    use_tls=use_tls,
                )
                subject = f"Reply to your message: {msg.subject or 'No subject'}"
                admin_name = getattr(getattr(request, "user", None), "get_full_name", lambda: "")() or getattr(request.user, "email", "") or "Admin"
                body = (
                    f"Hello {msg.name},\n\n"
                    f"Our team has replied to your message:\n\n"
                    f"{text.strip()}\n\n"
                    f"— {admin_name}\n"
                    f"{getattr(settings_obj, 'system_name', 'Construction License Management System')}"
                )
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=body,
                    from_email=user,
                    to=[msg.email],
                    reply_to=[getattr(settings_obj, "support_email", user) or user],
                    connection=connection,
                )
                email.send(fail_silently=True)
    except Exception as e:
        logger.warning("Failed to send contact reply email: %s", e)

    return Response(ser.data, status=status.HTTP_201_CREATED)
