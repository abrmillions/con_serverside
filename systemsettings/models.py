from django.db import models
from django.conf import settings as dj_settings


class SystemSettings(models.Model):
    system_name = models.CharField(max_length=255, default="Construction License Management System")
    support_email = models.EmailField(default="support@clms.gov")
    support_phone = models.CharField(max_length=64, default="+1-800-123-4567")

    # Feature toggles
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    auto_approval = models.BooleanField(default=False)
    maintenance_mode = models.BooleanField(default=False)
    document_verification_enabled = models.BooleanField(default=False)

    # Security
    session_timeout = models.IntegerField(default=30)
    max_login_attempts = models.IntegerField(default=5)
    password_min_length = models.IntegerField(default=8)

    # Email configuration
    smtp_host = models.CharField(max_length=255, default="smtp.example.com")
    smtp_port = models.IntegerField(default=587)
    smtp_user = models.CharField(max_length=255, default="noreply@clms.gov")
    smtp_password = models.CharField(max_length=255, default="", blank=True, null=True)
    use_tls = models.BooleanField(default=True)
    notification_template = models.TextField(
        default="Dear {name},\n\nYour application {id} has been {status}.\n\nThank you for using CLMS."
    )
    admin_ip_whitelist = models.TextField(default="", blank=True)
    gmail_client_id = models.CharField(max_length=255, default="", blank=True)
    gmail_client_secret = models.CharField(max_length=255, default="", blank=True)
    gmail_refresh_token = models.CharField(max_length=1024, default="", blank=True)
    use_gmail_oauth = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls):
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create()
        return obj

    def __str__(self):
        return f"SystemSettings (updated {self.updated_at})"
