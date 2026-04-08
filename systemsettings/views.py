from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from .models import SystemSettings
from .serializers import SystemSettingsSerializer
import os


@api_view(["GET"])
@permission_classes([AllowAny])
def maintenance_status_view(request):
    try:
        settings_obj = SystemSettings.get_solo()
        return Response({"maintenance_mode": settings_obj.maintenance_mode})
    except Exception:
        return Response({"maintenance_mode": False})

@api_view(["GET"])
@permission_classes([AllowAny])
def public_support_view(request):
    try:
        settings_obj = SystemSettings.get_solo()
        return Response({
            "system_name": getattr(settings_obj, "system_name", "") or "",
            "support_email": getattr(settings_obj, "support_email", "") or "",
            "support_phone": getattr(settings_obj, "support_phone", "") or "",
        })
    except Exception:
        return Response({
            "system_name": "",
            "support_email": "",
            "support_phone": "",
        })


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
                "use_gmail_oauth": False,
                "gmail_client_id": "",
                "gmail_client_secret": "",
                "gmail_refresh_token": "",
                "notification_template": "Dear {name}, \n \n Your application id  {id} has been {status}. \n \n Thank you for using CLMS.",
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
                
                # Apply AI keys to process environment for immediate effect
                # We still allow them to be persisted to DB via ser.save() 
                # unless explicitly popped for security reasons.
                # Here we ensure they are available in the current process.
                
                ai_keys = {
                    "deepseek_api_key": "DEEPSEEK_API_KEY",
                    "openrouter_api_key": "OPENROUTER_API_KEY",
                    "gemini_api_key": "GEMINI_API_KEY"
                }
                
                for key_field, env_var in ai_keys.items():
                    val = data.get(key_field)
                    if val is not None:
                        if val.strip():
                            os.environ[env_var] = val.strip()
                        else:
                            os.environ.pop(env_var, None)

                ser.save()
                return Response(ser.data)
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"detail": str(e) or "Settings error"}, status=status.HTTP_400_BAD_REQUEST)
