from django.http import JsonResponse
from systemsettings.models import SystemSettings
from django.urls import resolve

class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Get maintenance mode status from SystemSettings
        try:
            settings = SystemSettings.get_solo()
            is_maintenance = settings.maintenance_mode
        except Exception:
            is_maintenance = False

        if is_maintenance:
            # 2. Define path exclusions
            path = request.path
            
            # Allow admin panel
            if path.startswith('/admin/'):
                return self.get_response(request)
            
            # Allow system settings API so admins can turn it off
            if path.startswith('/api/system/settings/'):
                return self.get_response(request)
            
            # Allow public maintenance status
            if path.startswith('/api/system/maintenance/'):
                return self.get_response(request)

            # Allow Google OAuth endpoints
            if path.startswith('/api/users/google/'):
                return self.get_response(request)

            # Allow auth endpoints so admins can log in
            if '/api/users/token/' in path or '/api/users/token/refresh/' in path:
                return self.get_response(request)

            # 3. Block everything else for non-staff users
            if not request.user.is_authenticated or not request.user.is_staff:
                return JsonResponse(
                    {
                        "error": "maintenance_mode",
                        "message": "The system is currently in Maintenance in Progress updating. Please check back later."
                    },
                    status=503
                )

        return self.get_response(request)
