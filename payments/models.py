import uuid
from django.db import models
from django.conf import settings


class Payment(models.Model):
    STATUS_CHOICES = (("pending", "Pending"), ("success", "Success"), ("failed", "Failed"), ("active", "Active"))

    payer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="ETB")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    metadata = models.JSONField(blank=True, null=True)
    
    # New fields from migration 0004
    chapa_tx_id = models.CharField(max_length=120, blank=True, null=True)
    description = models.CharField(max_length=255, default="Construction License Payment")
    email = models.EmailField(blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    tx_ref = models.CharField(max_length=120, unique=True, default=uuid.uuid4)
    checkout_url = models.URLField(max_length=500, blank=True, null=True)
    receipt_url = models.URLField(max_length=500, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{getattr(self.payer, 'email', getattr(self.payer, 'username', 'payer'))} - {self.amount} {self.currency} ({self.status})"
