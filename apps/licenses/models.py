import uuid
from django.db import models
from django.conf import settings
from datetime import date


class License(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='licenses')
    application = models.OneToOneField('applications.Application', on_delete=models.SET_NULL, null=True, blank=True)
    license_type = models.CharField(max_length=100)
    license_number = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, default='active')
    issued_date = models.DateField()
    expiry_date = models.DateField()
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='issued_licenses')
    license_data = models.JSONField(blank=True, null=True)
    license_photo = models.ImageField(upload_to='license_photos/%Y/%m/%d/', blank=True, null=True)
    qr_code_data = models.CharField(max_length=255, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.license_type} - {self.license_number}"

    @property
    def is_active(self):
        return self.status == 'active' and self.expiry_date >= date.today()
