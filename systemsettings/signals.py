from django.contrib.auth.signals import user_login_failed, user_logged_in
from django.dispatch import receiver
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from .models import SystemSettings

# Cache key template for failed login attempts
# Format: login_attempts:<username>:<ip_address>
CACHE_KEY_TEMPLATE = "login_attempts:{}:{}"

@receiver(user_login_failed)
def track_failed_login_attempts(sender, credentials, request, **kwargs):
    username = credentials.get('username') or credentials.get('email')
    if not username:
        return
        
    ip_address = request.META.get('REMOTE_ADDR')
    cache_key = CACHE_KEY_TEMPLATE.format(username, ip_address)
    
    attempts = cache.get(cache_key, 0)
    attempts += 1
    
    # Cache the failed attempts for 1 hour
    cache.set(cache_key, attempts, timeout=3600)
    
    try:
        settings_obj = SystemSettings.get_solo()
        max_attempts = settings_obj.max_login_attempts
    except Exception:
        max_attempts = 5
        
    if attempts >= max_attempts:
        # Optionally lock the user account or log the security event
        pass

@receiver(user_logged_in)
def clear_failed_login_attempts(sender, request, user, **kwargs):
    username = user.username or user.email
    ip_address = request.META.get('REMOTE_ADDR')
    cache_key = CACHE_KEY_TEMPLATE.format(username, ip_address)
    cache.delete(cache_key)
