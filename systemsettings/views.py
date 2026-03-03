from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from .models import SystemSettings
from .serializers import SystemSettingsSerializer
import os


@api_view(["GET", "PATCH"])
@permission_classes([IsAdminUser])
def system_settings_view(request):
    try:
        settings_obj = SystemSettings.get_solo()
    except Exception:
        if request.method == "GET":
            return Response({
                "system_name": "Construction License Management System",
                "support_email": "support@clms.gov",
                "support_phone": "+1-800-123-4567",
                "email_notifications": True,
                "sms_notifications": False,
                "auto_approval": False,
                "maintenance_mode": False,
                "session_timeout": 30,
                "max_login_attempts": 5,
                "password_min_length": 8,
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "smtp_user": "noreply@clms.gov",
                "use_tls": True,
                "notification_template": "Dear {name},\n\nYour application {id} has been {status}.\n\nThank you for using CLMS.",
                "updated_at": None,
            })
        try:
            settings_obj = SystemSettings()
            settings_obj.save()
        except Exception:
            return Response({"detail": "Settings storage unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    try:
        if request.method == "GET":
            ser = SystemSettingsSerializer(settings_obj)
            return Response(ser.data)
        elif request.method == "PATCH":
            ser = SystemSettingsSerializer(settings_obj, data=request.data, partial=True)
            if ser.is_valid():
                data = ser.validated_data
                # Never persist the OpenAI key to DB; apply to process env only
                try:
                    key = data.pop("openai_api_key", None)
                    if key is not None:
                        if key.strip():
                            os.environ["OPENAI_API_KEY"] = key.strip()
                        else:
                            try:
                                del os.environ["OPENAI_API_KEY"]
                            except KeyError:
                                pass
                except Exception:
                    pass
                ser.save()
                # write_only fields won't be returned
                return Response(ser.data)
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"detail": str(e) or "Settings error"}, status=status.HTTP_400_BAD_REQUEST)
