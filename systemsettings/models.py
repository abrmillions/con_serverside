from django.db import models
from django.conf import settings as dj_settings


class SystemSettings(models.Model):
    system_name = models.CharField(max_length=255, default="Construction License Management System")
    support_email = models.EmailField(default="support@clms.gov")
    support_phone = models.CharField(max_length=64, default="+1-800-123-4567")

    # Feature toggles
    email_notifications = models.BooleanField(default=True)
    email_debug_mode = models.BooleanField(
        default=False,
        help_text="If enabled, emails will be printed to the console instead of being sent."
    )
    sms_notifications = models.BooleanField(default=False)
    auto_approval = models.BooleanField(default=False)
    maintenance_mode = models.BooleanField(default=False)
    document_verification_enabled = models.BooleanField(default=False)

    # Security
    session_timeout = models.IntegerField(default=30)
    max_login_attempts = models.IntegerField(default=5)
    password_min_length = models.IntegerField(default=8)
    two_factor_authentication_enabled = models.BooleanField(default=False)
    ip_whitelist_enabled = models.BooleanField(default=False)

    # SMTP settings
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.IntegerField(default=587, blank=True, null=True)
    smtp_user = models.CharField(max_length=255, blank=True)
    smtp_password = models.CharField(max_length=255, blank=True)
    smtp_use_tls = models.BooleanField(default=True)
    smtp_use_ssl = models.BooleanField(default=False)
    smtp_timeout = models.IntegerField(default=10, help_text="Timeout in seconds for SMTP connection.")

    notification_template = models.TextField(
        default="""Dear {name}, 
 
 Your application id  {id} has been {status}. 
 
 Thank you for using CLMS."""
    )
    admin_ip_whitelist = models.TextField(default="", blank=True)
    
    # AI verification configuration
    preferred_ai_provider = models.CharField(
        max_length=20,
        choices=(("deepseek", "DeepSeek"), ("gemini", "Gemini"), ("openrouter", "OpenRouter")),
        default="deepseek",
        help_text="Switch between DeepSeek, Gemini and OpenRouter for document verification"
    )
    
    deepseek_api_key = models.CharField(
        max_length=255, 
        default="", 
        blank=True, 
        help_text="DeepSeek API key for document verification"
    )
    deepseek_model = models.CharField(
        max_length=50,
        default="deepseek-chat",
        help_text="DeepSeek model to use: deepseek-chat or deepseek-reasoner"
    )
    deepseek_timeout = models.IntegerField(
        default=60,
        help_text="Timeout in seconds for DeepSeek API calls"
    )
    deepseek_max_retries = models.IntegerField(
        default=3,
        help_text="Maximum number of retries for failed DeepSeek API calls"
    )

    # OpenRouter configuration
    openrouter_api_key = models.CharField(
        max_length=255,
        default="",
        blank=True,
        help_text="OpenRouter API key for document verification"
    )
    openrouter_model = models.CharField(
        max_length=100,
        default="google/gemini-2.0-flash-001",
        help_text="OpenRouter model to use (e.g., google/gemini-2.0-flash-001, meta-llama/llama-3-70b-instruct, etc.)"
    )
    openrouter_timeout = models.IntegerField(
        default=60,
        help_text="Timeout in seconds for OpenRouter API calls"
    )

    # Gemini configuration
    gemini_api_key = models.CharField(
        max_length=255,
        default="",
        blank=True,
        help_text="Gemini API key for document verification"
    )
    gemini_model = models.CharField(
        max_length=50,
        default="gemini-2.0-flash",
        help_text="Gemini model to use (e.g., gemini-2.0-flash, gemini-1.5-pro, etc.)"
    )
    gemini_timeout = models.IntegerField(
        default=60,
        help_text="Timeout in seconds for Gemini API calls"
    )

    # Chapa Payment Integration
    chapa_secret_key = models.CharField(max_length=255, default="", blank=True, help_text="Chapa API secret key")
    chapa_base_url = models.URLField(default="https://api.chapa.co/v1", help_text="Chapa API base URL")
    chapa_webhook_secret = models.CharField(max_length=255, default="", blank=True)

    # Document verification settings
    min_document_resolution = models.IntegerField(default=300)
    max_document_size_mb = models.IntegerField(default=10)
    allowed_document_types = models.TextField(default="pdf,jpg,jpeg,png,gif")

    # OCR Settings
    ocr_language = models.CharField(
        max_length=50,
        default="amh+eng",
        help_text="Tesseract OCR language packs (e.g., 'amh+eng' for Amharic+English)"
    )
    ocr_timeout = models.IntegerField(
        default=30,
        help_text="Timeout in seconds for OCR processing"
    )

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=255, blank=True, null=True)

    @classmethod
    def get_solo(cls):
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create()
        return obj

    def get_deepseek_config(self):
        return {
            "api_key": self.deepseek_api_key,
            "model": self.deepseek_model,
            "timeout": self.deepseek_timeout,
            "max_retries": self.deepseek_max_retries
        }

    def __str__(self):
        return f"SystemSettings (updated {self.updated_at})"

    class Meta:
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"
