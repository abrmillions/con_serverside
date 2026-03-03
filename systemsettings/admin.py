from django.contrib import admin
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.conf import settings
from django.urls import reverse
from .models import SystemSettings

@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def changelist_view(self, request, extra_context=None):
        if not self._is_allowed(request):
            return HttpResponseForbidden("Forbidden")
        obj = SystemSettings.get_solo()
        return HttpResponseRedirect(
            reverse("admin:systemsettings_systemsettings_change", args=(obj.id,))
        )

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if not self._is_allowed(request):
            return HttpResponseForbidden("Forbidden")
        ip = self._client_ip(request)
        wl_model = SystemSettings.get_solo().admin_ip_whitelist or ""
        wl_cfg = [ip.strip() for ip in wl_model.split(",") if ip.strip()]
        extra_context = extra_context or {}
        extra_context["title"] = f"System settings (client IP: {ip})"
        extra_context["ip_whitelist"] = ", ".join(wl_cfg)
        return super().change_view(request, object_id, form_url, extra_context)

    def _is_allowed(self, request):
        wl_model = SystemSettings.get_solo().admin_ip_whitelist or ""
        wl_cfg = [ip.strip() for ip in wl_model.split(",") if ip.strip()]
        wl_env = getattr(settings, "ADMIN_IP_WHITELIST", None)
        wl = wl_cfg or wl_env
        if not wl:
            return True
        ip = self._client_ip(request)
        return ip in wl

    def _client_ip(self, request):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
