from django.db import models
from django.conf import settings


class ContactMessage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="contact_messages")
    name = models.CharField(max_length=255)
    email = models.EmailField()
    subject = models.CharField(max_length=255, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=20, default="open")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.email} - {self.subject or 'No subject'}"


class ContactReply(models.Model):
    message = models.ForeignKey(ContactMessage, on_delete=models.CASCADE, related_name="replies")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    sender_type = models.CharField(max_length=10, choices=(("user", "user"), ("admin", "admin")))
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    send_status = models.CharField(
        max_length=16,
        default="pending",
        choices=(
            ("pending", "pending"),
            ("success", "success"),
            ("warning", "warning"),
            ("error", "error"),
        ),
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    send_error = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Reply by {self.sender_type} on {self.message_id}"
