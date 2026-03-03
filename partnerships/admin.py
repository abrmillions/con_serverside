from django.contrib import admin
from django.utils.html import format_html
from .models import Partnership, PartnershipDocument, PartnershipApprovalLog

class PartnershipDocumentInline(admin.TabularInline):
    model = PartnershipDocument
    fields = ("document_type", "file_link", "uploaded_at")
    readonly_fields = ("file_link", "uploaded_at")
    extra = 0

    def file_link(self, obj):
        try:
            storage = obj.file.storage
            if not storage.exists(obj.file.name):
                return format_html('<span style="color: #c00;">Missing file</span>')
            return format_html('<a href="{}" target="_blank" rel="noopener">Download</a>', obj.file.url)
        except Exception:
            return "-"

class PartnershipApprovalLogInline(admin.TabularInline):
    model = PartnershipApprovalLog
    fields = ("action",)
    readonly_fields = ()
    extra = 1
    can_delete = False

    def get_queryset(self, request):
        return PartnershipApprovalLog.objects.none()

@admin.register(Partnership)
class PartnershipAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "main_contractor", "partner_company", "status", "certificate_number", "created_at")
    list_filter = ("status", "partnership_type")
    search_fields = ("certificate_number", "main_contractor__name", "partner_company__name", "owner__email")
    inlines = (PartnershipDocumentInline, PartnershipApprovalLogInline)
    fields = (
        "owner",
        "main_contractor",
        "partner_company",
        "partnership_type",
        "ownership_ratio_main",
        "ownership_ratio_partner",
        "status",
        "start_date",
        "end_date",
        "qr_code",
        "certificate_number",
        "registration_data",
        "partners_data",
    )
