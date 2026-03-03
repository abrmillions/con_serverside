from rest_framework import serializers
from .models import SystemSettings


class SystemSettingsSerializer(serializers.ModelSerializer):
    smtp_password = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    openai_api_key = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    class Meta:
        model = SystemSettings
        fields = (
            "system_name",
            "support_email",
            "support_phone",
            "email_notifications",
            "sms_notifications",
            "auto_approval",
            "maintenance_mode",
            "document_verification_enabled",
            "session_timeout",
            "max_login_attempts",
            "password_min_length",
            "smtp_host",
            "smtp_port",
            "smtp_user",
            "smtp_password",
            "openai_api_key",
            "use_tls",
            "notification_template",
            "updated_at",
        )
        extra_kwargs = {
            "smtp_password": {"write_only": True, "required": False},
            "openai_api_key": {"write_only": True, "required": False},
        }
