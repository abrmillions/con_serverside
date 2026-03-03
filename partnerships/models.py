from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class Company(models.Model):
    id = models.AutoField(primary_key=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="companies")
    name = models.CharField(max_length=255)
    registration_number = models.CharField(max_length=64, blank=True, null=True)
    license_number = models.CharField(max_length=64, blank=True, null=True)
    license_expiry_date = models.DateField(blank=True, null=True)
    country = models.CharField(max_length=64, blank=True, null=True)
    status = models.CharField(max_length=20, choices=(("active", "Active"), ("suspended", "Suspended")), default="active")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def license_valid(self) -> bool:
        try:
            not_expired = True
            if self.license_expiry_date:
                not_expired = self.license_expiry_date >= timezone.localdate()
            return bool(self.license_number) and self.status == "active" and not_expired
        except Exception:
            return bool(self.license_number) and self.status == "active"


class Partnership(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("awaiting_partner_approval", "Awaiting Partner Approval"),
        ("awaiting_government_review", "Awaiting Government Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("active", "Active"),
        ("suspended", "Suspended"),
        ("expired", "Expired"),
    )

    PARTNERSHIP_TYPES = (
        ("joint_venture", "Joint Venture"),
        ("subcontract", "Subcontract"),
        ("foreign_local", "Foreign-Local"),
        ("consortium", "Consortium"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="partnerships")
    main_contractor = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="main_partnerships", null=True, blank=True)
    partner_company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="partner_partnerships", null=True, blank=True)
    partnership_type = models.CharField(max_length=32, choices=PARTNERSHIP_TYPES, default="joint_venture")
    ownership_ratio_main = models.DecimalField(max_digits=5, decimal_places=2, default=60)
    ownership_ratio_partner = models.DecimalField(max_digits=5, decimal_places=2, default=40)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="pending")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    qr_code = models.ImageField(upload_to="qr/partnerships/", null=True, blank=True)
    certificate_number = models.CharField(max_length=64, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    registration_data = models.JSONField(blank=True, null=True)
    partners_data = models.JSONField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner"], name="unique_partnership_per_owner"),
        ]

    def __str__(self):
        return f"{self.main_contractor.name} + {self.partner_company.name}"

    @property
    def is_foreign(self) -> bool:
        try:
            return (self.main_contractor.country or "").lower() != (self.partner_company.country or "").lower()
        except Exception:
            return False

    def check_expiry_and_update(self):
        if self.end_date and self.end_date < timezone.localdate():
            if self.status != "expired":
                self.status = "expired"
                self.save(update_fields=["status"])

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class PartnershipDocument(models.Model):
    partnership = models.ForeignKey(Partnership, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=64)
    file = models.FileField(upload_to="partnerships/documents/")
    uploaded_at = models.DateTimeField(auto_now_add=True)


class PartnershipApprovalLog(models.Model):
    partnership = models.ForeignKey(Partnership, on_delete=models.CASCADE, related_name="approval_logs")
    action = models.CharField(max_length=64)  # created, partner_accepted, approved, rejected, suspended
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    actor_role = models.CharField(max_length=32, blank=True, null=True)  # Contractor, Partner, Officer
    actor_identifier = models.CharField(max_length=64, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
