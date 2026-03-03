from django.db import models
from django.conf import settings


class Payment(models.Model):
    STATUS_CHOICES = (("pending", "Pending"), ("completed", "Completed"), ("failed", "Failed"), ("active", "Active"))

    payer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    metadata = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{getattr(self.payer, 'email', getattr(self.payer, 'username', 'payer'))} - {self.amount} {self.currency} ({self.status})"
