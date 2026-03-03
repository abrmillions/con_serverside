from django.apps import AppConfig


class LicenseHistoryConfig(AppConfig):
    name = "license_history"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import signals  # noqa
