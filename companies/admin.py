from django.contrib import admin, messages
from django.utils.html import format_html
from django.urls import reverse
from django.shortcuts import redirect
from .models import Company
from applications.models import Application


class ApplicationInline(admin.TabularInline):
    model = Application
    fields = ("id", "license_type", "status", "created_at", "open")
    readonly_fields = ("id", "license_type", "status", "created_at", "open")
    extra = 0

    def open(self, obj):
        try:
            url = reverse("admin:applications_application_change", args=[obj.pk])
            return format_html('<a href="{}">Open</a>', url)
        except Exception:
            return "-"
    open.short_description = "View"


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "registration_number", "applications_count", "is_active", "created_at")
    search_fields = ("name", "registration_number", "email")
    list_filter = ("is_active", "city", "state")
    readonly_fields = ("id", "created_at", "updated_at", "registration_date", "applications_link")
    ordering = ("-created_at",)
    inlines = (ApplicationInline,)
    actions = ("create_contractor_application",)

    def applications_count(self, obj):
        try:
            return obj.applications.count()
        except Exception:
            return 0
    applications_count.short_description = "Applications"

    def applications_link(self, obj):
        try:
            url = reverse("admin:applications_application_changelist")
            return format_html('<a href="{}?company__id__exact={}">View Applications</a>', url, obj.pk)
        except Exception:
            return "-"
    applications_link.short_description = "Applications List"

    def create_contractor_application(self, request, queryset):
        if queryset.count() != 1:
            messages.error(request, "Select exactly one company to create an application.")
            return
        company = queryset.first()
        url = f'{reverse("admin:applications_application_add")}?company={company.pk}&license_type=Contractor%20License'
        return redirect(url)
    create_contractor_application.short_description = "Create Contractor Application for selected company"
