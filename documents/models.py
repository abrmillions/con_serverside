from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.html import format_html


def document_upload_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/documents/<email>/<filename>
    email = instance.uploader.email if instance.uploader else "anonymous"
    return f"documents/{email}/{filename}"


class Document(models.Model):
    uploader = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="documents")
    file = models.FileField(upload_to=document_upload_path, verbose_name="File Link")
    name = models.CharField(max_length=255, blank=True, verbose_name="Document Type")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    verification_status = models.CharField(max_length=32, blank=True, default="", db_index=True)
    verification_score = models.FloatField(null=True, blank=True)
    verification_details = models.TextField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    vehicle = models.ForeignKey(
        "vehicles.Vehicle",
        on_delete=models.CASCADE,
        related_name="documents",
        blank=True,
        null=True,
    )
    application = models.ForeignKey(
        "applications.Application",
        on_delete=models.CASCADE,
        related_name="documents",
        blank=True,
        null=True,
    )

    def __str__(self):
        return self.name or self.file.name

    def file_link(self):
        try:
            if self.file and hasattr(self.file, "url"):
                return format_html('<a href="{}" target="_blank">Download</a>', self.file.url)
        except Exception:
            return ""
        return ""
    file_link.short_description = "File Link"

    def save(self, *args, **kwargs):
        try:
            if (not self.name or not str(self.name).strip()) and self.file and getattr(self.file, "name", None):
                # Default name to basename of file if not provided
                base = str(self.file.name).split("/")[-1]
                self.name = base
        except Exception:
            pass
        super().save(*args, **kwargs)


class DocumentAccessLog(models.Model):
    ACTION_CHOICES = (
        ("download", "Download"),
        ("view", "View"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    document = models.ForeignKey("Document", on_delete=models.CASCADE, related_name="access_logs", null=True, blank=True)
    application = models.ForeignKey("applications.Application", on_delete=models.CASCADE, related_name="document_access_logs", null=True, blank=True)
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(default=timezone.now)
    details = models.TextField(blank=True)

    class Meta:
        ordering = ("-timestamp",)

    def __str__(self):
        who = self.user.email if self.user else "(anonymous)"
        return f"{who} {self.action} {self.document or self.application} @ {self.timestamp.isoformat()}"
