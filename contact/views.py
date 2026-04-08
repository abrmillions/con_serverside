from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import ContactMessage, ContactReply
from .serializers import ContactMessageSerializer, ContactReplySerializer
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from systemsettings.models import SystemSettings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def send_smtp_email(settings, to_email, subject, html_body, text_body):
    print(f"DEBUG: Attempting to send email to {to_email} via {settings.smtp_host}:{settings.smtp_port}")
    connection = get_connection(
        backend='django.core.mail.backends.smtp.EmailBackend',
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        use_tls=settings.smtp_use_tls,
        use_ssl=getattr(settings, 'smtp_use_ssl', False),
        timeout=getattr(settings, 'smtp_timeout', 10)
    )
    from_name = getattr(settings, 'system_name', 'Support')
    from_email = f"{from_name} <{settings.support_email}>"
    
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=from_email,
        to=[to_email],
        reply_to=[settings.support_email],
        connection=connection
    )
    email.attach_alternative(html_body, "text/html")
    result = email.send(fail_silently=False)
    print(f"DEBUG: Email send result: {result}")
    return result


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
    
    # GET logic: allow any authenticated user to list all messages
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
    qs = ContactMessage.objects.order_by("-created_at")
    ser = ContactMessageSerializer(qs, many=True)
    return Response(ser.data)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([AllowAny])
def message_detail_view(request, pk):
    print(f"\n--- DEBUG message_detail_view ---")
    print(f"Method: {request.method}")
    print(f"PK: {pk}")
    
    if request.method == "DELETE":
        try:
            # More robust deletion
            deleted_count, _ = ContactMessage.objects.filter(id=pk).delete()
            print(f"Deleted count: {deleted_count}")
            return Response({"detail": "Deleted"}, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"DELETE ERROR: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    msg = get_object_or_404(ContactMessage, pk=pk)
    print(f"Found message: {msg.subject}")
    if request.method == "GET":
        ser = ContactMessageSerializer(msg)
        return Response(ser.data)
    elif request.method == "PATCH":
        ser = ContactMessageSerializer(msg, data=request.data, partial=True)
        if ser.is_valid():
            ser.save()
            return Response(ser.data)
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([AllowAny])
def reply_detail_view(request, pk):
    if request.method == "DELETE":
        try:
            ContactReply.objects.filter(id=pk).delete()
            return Response({"detail": "Deleted"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    rep = get_object_or_404(ContactReply, pk=pk)
    if request.method == "GET":
        ser = ContactReplySerializer(rep)
        return Response(ser.data)
    elif request.method == "PATCH":
        text = request.data.get("text")
        if not text:
            return Response({"detail": "Text required"}, status=status.HTTP_400_BAD_REQUEST)
        rep.text = text
        rep.save(update_fields=["text"])
        ser = ContactReplySerializer(rep)
        return Response(ser.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reply_view(request, pk: int):
    msg = get_object_or_404(ContactMessage, pk=pk)
    
    text = request.data.get("text") or request.data.get("message") or ""
    if not text.strip():
        return Response({"detail": "Reply text required"}, status=status.HTTP_400_BAD_REQUEST)
    
    rep = ContactReply.objects.create(
        message=msg, 
        sender=request.user, 
        sender_type="admin", 
        text=text.strip()
    )
    ser = ContactReplySerializer(rep)
    msg.status = "open"
    msg.save(update_fields=["status"])

    try:
        settings_obj = SystemSettings.get_solo()
        if getattr(settings_obj, "email_notifications", True):
            if getattr(settings_obj, "email_debug_mode", False):
                print("\n" + "="*50)
                print("DEBUG EMAIL (API Reply)")
                print(f"To: {msg.email}")
                print(f"Subject: Reply to your message: {msg.subject or 'No subject'}")
                print(f"Body:\n{text.strip()}")
                print("="*50 + "\n")
                rep.send_status = "success"
                rep.save(update_fields=["send_status"])
                return Response(ser.data, status=status.HTTP_201_CREATED)

            subject = f"Reply to your message: {msg.subject or 'No subject'}"
            admin_name = getattr(getattr(request, "user", None), "get_full_name", lambda: "")() or getattr(request.user, "email", "") or "Admin"
            
            html_body = render_to_string(
                "email/contact_reply.html",
                {
                    "name": msg.name,
                    "text": text.strip(),
                    "admin_name": admin_name,
                    "system_name": getattr(settings_obj, "system_name", "Construction License Management System"),
                },
            )
            text_body = (
                f"Hello {msg.name},\n\n"
                f"Our support team has replied to your message regarding {getattr(settings_obj, 'system_name', 'our system')}:\n\n"
                f"\"{text.strip()}\"\n\n"
                f"Best regards,\n"
                f"{admin_name}\n"
                f"{getattr(settings_obj, 'system_name', 'Support')} Team\n\n"
                f"---\n"
                f"You are receiving this email because you sent a message to the {getattr(settings_obj, 'system_name', 'Support')} contact form."
            )
            
            try:
                send_smtp_email(settings_obj, msg.email, subject, html_body, text_body)
                rep.send_status = "success"
                rep.sent_at = timezone.now()
                rep.save(update_fields=["send_status", "sent_at"])
            except Exception as e:
                logger.error(f"Email sending failed: {str(e)}")
                print(f"DEBUG: Email sending error: {str(e)}")
                rep.send_status = "error"
                rep.send_error = str(e)
                rep.save(update_fields=["send_status", "send_error"])
    except Exception as e:
        logger.error(f"Reply email failed: {e}")
    
    return Response(ser.data, status=status.HTTP_201_CREATED)
