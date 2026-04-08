from rest_framework import serializers
from .models import SystemSettings
import ipaddress


class SystemSettingsSerializer(serializers.ModelSerializer):
    # Make sensitive fields write-only
    deepseek_api_key = serializers.CharField(
        write_only=True, 
        required=False, 
        allow_blank=True, 
        allow_null=True,
        style={'input_type': 'password'}
    )
    chapa_secret_key = serializers.CharField(
        write_only=True, 
        required=False, 
        allow_blank=True, 
        allow_null=True,
        style={'input_type': 'password'}
    )
    chapa_webhook_secret = serializers.CharField(
        write_only=True, 
        required=False, 
        allow_blank=True, 
        allow_null=True,
        style={'input_type': 'password'}
    )
    gemini_api_key = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
        style={'input_type': 'password'}
    )
    openrouter_api_key = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
        style={'input_type': 'password'}
    )
    
    # Read-only fields for display (masked)
    deepseek_api_key_display = serializers.SerializerMethodField()
    chapa_secret_key_display = serializers.SerializerMethodField()
    gemini_api_key_display = serializers.SerializerMethodField()
    openrouter_api_key_display = serializers.SerializerMethodField()
    
    # Validation for integer fields
    session_timeout = serializers.IntegerField(min_value=1, max_value=1440, required=False)
    max_login_attempts = serializers.IntegerField(min_value=1, max_value=50, required=False)
    password_min_length = serializers.IntegerField(min_value=4, max_value=128, required=False)
    deepseek_timeout = serializers.IntegerField(min_value=5, max_value=300, required=False)
    deepseek_max_retries = serializers.IntegerField(min_value=0, max_value=10, required=False)
    gemini_timeout = serializers.IntegerField(min_value=5, max_value=300, required=False)
    openrouter_timeout = serializers.IntegerField(min_value=5, max_value=300, required=False)
    min_document_resolution = serializers.IntegerField(min_value=72, max_value=1200, required=False)
    max_document_size_mb = serializers.IntegerField(min_value=1, max_value=100, required=False)
    ocr_timeout = serializers.IntegerField(min_value=5, max_value=120, required=False)

    # CamelCase aliases for frontend compatibility
    deepseekApiKey = serializers.CharField(source="deepseek_api_key", write_only=True, required=False, allow_blank=True, allow_null=True)
    openrouterApiKey = serializers.CharField(source="openrouter_api_key", write_only=True, required=False, allow_blank=True, allow_null=True)
    openrouterModel = serializers.CharField(source="openrouter_model", required=False, allow_blank=True, allow_null=True)
    openrouterTimeout = serializers.IntegerField(source="openrouter_timeout", min_value=5, max_value=300, required=False)
    geminiApiKey = serializers.CharField(source="gemini_api_key", write_only=True, required=False, allow_blank=True, allow_null=True)
    geminiModel = serializers.CharField(source="gemini_model", required=False, allow_blank=True, allow_null=True)
    geminiTimeout = serializers.IntegerField(source="gemini_timeout", min_value=5, max_value=300, required=False)
    preferredAiProvider = serializers.CharField(source="preferred_ai_provider", required=False, allow_blank=True, allow_null=True)
    twoFactorAuthenticationEnabled = serializers.BooleanField(source="two_factor_authentication_enabled", required=False)
    ipWhitelistEnabled = serializers.BooleanField(source="ip_whitelist_enabled", required=False)

    class Meta:
        model = SystemSettings
        fields = (
            # System Info
            "system_name",
            "support_email",
            "support_phone",
            
            # Feature Toggles
            "email_notifications",
            "email_debug_mode",
            "sms_notifications",
            "auto_approval",
            "maintenance_mode",
            "document_verification_enabled",
            
            # Security
            "session_timeout",
            "max_login_attempts",
            "password_min_length",
            "two_factor_authentication_enabled",
            "ip_whitelist_enabled",
            "twoFactorAuthenticationEnabled",
            "ipWhitelistEnabled",
            "admin_ip_whitelist",
            
            # Email
            "notification_template",
            "smtp_host",
            "smtp_port",
            "smtp_user",
            "smtp_password",
            "smtp_use_tls",
            "smtp_use_ssl",
            "smtp_timeout",
            
            # DeepSeek AI
            "preferred_ai_provider",
            "preferredAiProvider",
            "deepseek_api_key",
            "deepseek_api_key_display",
            "deepseek_model",
            "deepseek_timeout",
            "deepseek_max_retries",
            "deepseekApiKey",
            
            # OpenRouter
            "openrouter_api_key",
            "openrouter_api_key_display",
            "openrouter_model",
            "openrouter_timeout",
            "openrouterApiKey",
            "openrouter_model",
            "openrouterModel",
            "openrouterTimeout",

            # Gemini
            "gemini_api_key",
            "gemini_api_key_display",
            "gemini_model",
            "gemini_timeout",
            "geminiApiKey",
            "geminiModel",
            "geminiTimeout",
            
            # Chapa Payment
            "chapa_secret_key",
            "chapa_secret_key_display",
            "chapa_base_url",
            "chapa_webhook_secret",
            
            # Document Settings
            "min_document_resolution",
            "max_document_size_mb",
            "allowed_document_types",
            
            # OCR Settings
            "ocr_language",
            "ocr_timeout",
            
            # Audit
            "updated_at",
            "updated_by",
        )
        read_only_fields = ("updated_at",)
        extra_kwargs = {
            "updated_by": {"read_only": True},
            "admin_ip_whitelist": {"required": False, "allow_blank": True},
            "notification_template": {"required": False, "allow_blank": True},
            "allowed_document_types": {"required": False, "allow_blank": True},
            "ocr_language": {"required": False, "allow_blank": True},
        }

    def get_deepseek_api_key_display(self, obj):
        if obj.deepseek_api_key:
            return "••••••••" + obj.deepseek_api_key[-4:] if len(obj.deepseek_api_key) > 4 else "••••••••"
        return None

    def get_chapa_secret_key_display(self, obj):
        if obj.chapa_secret_key:
            return "••••••••" + obj.chapa_secret_key[-4:] if len(obj.chapa_secret_key) > 4 else "••••••••"
        return None

    def get_gemini_api_key_display(self, obj):
        if obj.gemini_api_key:
            return "••••••••" + obj.gemini_api_key[-4:] if len(obj.gemini_api_key) > 4 else "••••••••"
        return None

    def get_openrouter_api_key_display(self, obj):
        if hasattr(obj, 'openrouter_api_key') and obj.openrouter_api_key:
            return "••••••••" + obj.openrouter_api_key[-4:] if len(obj.openrouter_api_key) > 4 else "••••••••"
        return None

    def validate_admin_ip_whitelist(self, value):
        if not value:
            return value
        ips = [ip.strip() for ip in value.split(',') if ip.strip()]
        invalid_ips = []
        for ip in ips:
            try:
                ipaddress.ip_address(ip)
            except ValueError:
                try:
                    ipaddress.ip_network(ip, strict=False)
                except ValueError:
                    invalid_ips.append(ip)
        if invalid_ips:
            raise serializers.ValidationError(f"Invalid IP addresses: {', '.join(invalid_ips)}")
        return value

    def validate_allowed_document_types(self, value):
        if not value:
            return value
        extensions = [ext.strip().lower() for ext in value.split(',') if ext.strip()]
        valid_extensions = ['pdf', 'jpg', 'jpeg', 'png', 'gif', 'tiff', 'bmp', 'webp']
        invalid_exts = [ext for ext in extensions if ext not in valid_extensions]
        if invalid_exts:
            raise serializers.ValidationError(f"Invalid extensions: {', '.join(invalid_exts)}")
        return value

    def validate_deepseek_model(self, value):
        valid_models = ['deepseek-chat', 'deepseek-reasoner']
        if value and value not in valid_models:
            raise serializers.ValidationError(f"Invalid model. Choose: {', '.join(valid_models)}")
        return value
