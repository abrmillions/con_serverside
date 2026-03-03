from django.contrib import admin
from django.utils.html import format_html
from .models import Document
from .models import DocumentAccessLog
from .utils import infer_document_name


@admin.register(DocumentAccessLog)
class DocumentAccessLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "document", "application", "action", "timestamp")
    search_fields = ("user__email", "document__name", "application__applicant__email")
    readonly_fields = ("user", "document", "application", "action", "timestamp", "details")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "uploader", "uploaded_at", "application", "vehicle", "file_link")
    search_fields = ("name", "uploader__email")
    readonly_fields = ("file_link",)
    actions = ("normalize_names",)

    def file_link(self, obj):
        try:
            # Check that the file actually exists on disk/storage
            storage = obj.file.storage
            if not storage.exists(obj.file.name):
                return format_html('<span style="color: #c00;">Missing file</span>')
            url = obj.file.url
            return format_html('<a href="{}" target="_blank" rel="noopener">Download</a>', url)
        except Exception:
            return "-"

    file_link.short_description = "File"

    def normalize_names(self, request, queryset):
        updated = 0
        for doc in queryset:
            try:
                current = (doc.name or "").strip()
                source = current or getattr(doc.file, "name", "")
                inferred = infer_document_name(source)
                if inferred and inferred != current:
                    doc.name = inferred
                    doc.save(update_fields=["name"])
                    updated += 1
            except Exception:
                continue
        self.message_user(request, f"Updated {updated} document names.")
    normalize_names.short_description = "Normalize document names"
