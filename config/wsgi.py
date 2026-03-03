import os
from django.core.wsgi import get_wsgi_application
from django.conf import settings
from whitenoise import WhiteNoise
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()

# Only wrap with WhiteNoise when not in DEBUG and static directory exists
try:
    if not settings.DEBUG:
        static_root = Path(str(getattr(settings, "STATIC_ROOT", "")))
        if static_root and static_root.exists():
            application = WhiteNoise(application, root=str(static_root))
except Exception:
    # Fail open in development-like scenarios
    pass
