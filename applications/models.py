from django.db import models
from django.conf import settings
from licenses.models import License


class Application(models.Model):
    LICENSE_TYPE_CHOICES = (
        ("Contractor License", "Contractor License"),
        ("Professional License", "Professional License"),
        ("Import/Export License", "Import/Export License"),
    )   

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("info_requested", "Info Requested"),
        ("resubmitted", "Resubmitted"),
    )

    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications")
    license_type = models.CharField(max_length=50, choices=LICENSE_TYPE_CHOICES)
    data = models.JSONField(blank=True, null=True)
    # Optional subtype for more specific license categorization (e.g., grade-a, specialized)
    subtype = models.CharField(max_length=50, blank=True, null=True)
    # Photos for different license types. Only one is required depending on license_type.
    profile_photo = models.ImageField(upload_to='application_photos/profile_photo/%Y/%m/%d/', blank=True, null=True)
    professional_photo = models.ImageField(upload_to='application_photos/professional_photo/%Y/%m/%d/', blank=True, null=True)
    company_representative_photo = models.ImageField(upload_to='application_photos/company_representative_photo/%Y/%m/%d/', blank=True, null=True)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, null=True, blank=True, related_name='applications')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_renewal = models.BooleanField(default=False)
    previous_license = models.ForeignKey(License, on_delete=models.SET_NULL, null=True, blank=True, related_name="renewal_applications")

    def approve(self):
        self.status = "approved"
        self.save()

    def reject(self):
        self.status = "rejected"
        self.save()

    def request_info(self):
        self.status = "info_requested"
        self.save()

    def __str__(self):
        return f"{self.applicant} - {self.license_type} ({self.status})"


class ApplicationLog(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="logs")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50)
    details = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.application} - {self.action} by {self.actor} at {self.timestamp}"


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="notifications", null=True, blank=True)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user}: {self.title}"
