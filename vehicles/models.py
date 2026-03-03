from django.db import models
from django.conf import settings
from django.utils import timezone


class Vehicle(models.Model):
    STATUS_CHOICES = (("active", "Active"), ("pending", "Pending"), ("inactive", "Inactive"))

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vehicles")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    data = models.JSONField(default=dict, blank=True)
    registered_at = models.DateTimeField(default=timezone.now)

    # Legacy fields
    vin = models.CharField(max_length=128, blank=True, null=True)
    make = models.CharField(max_length=128, blank=True, null=True)
    model = models.CharField(max_length=128, blank=True, null=True)
    year = models.IntegerField(blank=True, null=True)
    plate_number = models.CharField(max_length=64, blank=True, null=True, unique=True)
    chassis_number = models.CharField(max_length=64, blank=True, null=True, unique=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner"], name="unique_vehicle_per_owner"),
        ]

    def __str__(self):
        return f"Vehicle {self.id} - {getattr(self.owner, 'email', getattr(self.owner, 'username', 'owner'))}"

    def save(self, *args, **kwargs):
        try:
            if isinstance(self.data, dict):
                self.vin = self.vin or self.data.get("vin") or self.data.get("engineNumber")
                self.make = self.make or self.data.get("manufacturer")
                self.model = self.model or self.data.get("model")
                try:
                    yr = self.year or self.data.get("year")
                    if yr is not None:
                        self.year = int(yr)
                except Exception:
                    pass
                self.plate_number = self.plate_number or self.data.get("plateNumber")
                self.chassis_number = self.chassis_number or self.data.get("chassisNumber")
        except Exception:
            pass
        super().save(*args, **kwargs)
