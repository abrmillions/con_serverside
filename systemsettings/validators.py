from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from .models import SystemSettings

class DynamicPasswordMinLengthValidator:
    def validate(self, password, user=None):
        try:
            settings_obj = SystemSettings.get_solo()
            min_length = settings_obj.password_min_length
        except Exception:
            min_length = 8
            
        if len(password) < min_length:
            raise ValidationError(
                _("This password is too short. It must contain at least %(min_length)d characters."),
                code='password_too_short',
                params={'min_length': min_length},
            )

    def get_help_text(self):
        try:
            settings_obj = SystemSettings.get_solo()
            min_length = settings_obj.password_min_length
        except Exception:
            min_length = 8
            
        return _(
            "Your password must contain at least %(min_length)d characters."
            % {'min_length': min_length}
        )
