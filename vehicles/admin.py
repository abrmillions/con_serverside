from django.contrib import admin
from .models import Vehicle
from documents.models import Document


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("id", "vin", "owner", "make", "model", "year")
    search_fields = ("vin", "owner__username", "make", "model")
    readonly_fields = ()
    inlines = []

    class Media:
        css = {
            "all": ("admin/vehicle-ui.css",)
        }

    def get_inlines(self, request, obj=None):
        class DocumentInline(admin.TabularInline):
            model = Document
            extra = 0
            fields = ("name", "file", "uploaded_at")
            readonly_fields = ("uploaded_at",)
            fk_name = "vehicle"

            def formfield_for_dbfield(self, db_field, request, **kwargs):
                formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
                if db_field.name == "name":
                    formfield.label = "Document Type"
                if db_field.name == "file":
                    formfield.label = "File Link"
                return formfield
        return [DocumentInline]
