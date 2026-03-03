from django.db import models
from django.conf import settings
from datetime import date


class License(models.Model):
    LICENSE_TYPES = (
        ("Contractor License", "Contractor License"),
        ("Professional License", "Professional License"),
        ("Import/Export License", "Import/Export License"),
    )
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("active", "Active"),
        ("revoked", "Revoked"),
        ("expired", "Expired"),
        ("renewed", "Renewed"),
    )

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="licenses")
    license_type = models.CharField(max_length=50, choices=LICENSE_TYPES)
    license_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='issued_licenses')
    issued_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    data = models.JSONField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    license_photo = models.ImageField(upload_to='license_photos/%Y/%m/%d/', blank=True, null=True)
    qr_code_data = models.CharField(max_length=255, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    previous_license = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="renewals")
    company = models.ForeignKey('companies.Company', on_delete=models.SET_NULL, null=True, blank=True, related_name='company_licenses')
    replaces_license = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replaced_by_licenses')
    replacement_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{getattr(self.owner, 'email', getattr(self.owner, 'username', 'owner'))} - {self.license_type} ({self.status})"

    @property
    def is_active(self):
        if self.status != 'active':
            return False
        if self.expiry_date and self.expiry_date < date.today():
            return False
        return True

    def save(self, *args, **kwargs):
        try:
            if self.expiry_date and self.expiry_date < date.today() and self.status in ('active', 'approved'):
                self.status = 'expired'
            # Sync standardized date strings in data for frontend if missing
            if isinstance(self.data, dict):
                if self.issued_date and not self.data.get('issueDate'):
                    self.data['issueDate'] = self.issued_date.isoformat()
                if self.expiry_date and not self.data.get('expiryDate'):
                    self.data['expiryDate'] = self.expiry_date.isoformat()
                if self.license_number and not (self.data.get('licenseNumber') or self.data.get('registrationNumber')):
                    self.data['licenseNumber'] = self.license_number
        except Exception:
            pass
        super().save(*args, **kwargs)

    class Meta:
        # Ensure at the application level a user can only have one license per license_type
        # We also add a database-level constraint to help enforce correctness.
        constraints = [
            models.UniqueConstraint(fields=['owner', 'license_type'], name='unique_owner_license_type')
        ]
