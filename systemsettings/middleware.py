from datetime import timedelta
from django.utils.deprecation import MiddlewareMixin
from .models import SystemSettings

class DynamicSessionTimeoutMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.user.is_authenticated:
            try:
                settings_obj = SystemSettings.get_solo()
                timeout_minutes = settings_obj.session_timeout
                # Set session expiry for the current session
                request.session.set_expiry(timeout_minutes * 60)
            except Exception:
                pass
        return None
