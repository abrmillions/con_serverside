"""
Moved helper: logout unit test (moved from project root to avoid test discovery).
To run: `python backend/tools/logout_unit_test.py` from repo root.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIRequestFactory, force_authenticate
from users.views import LogoutView

User = get_user_model()

email = 'unit_test_user@example.com'
password = 'UnitTestPass123!'
user, created = User.objects.get_or_create(email=email, defaults={'username': 'unittestuser', 'first_name': 'Unit',})
if created:
    user.set_password(password)
    user.save()

# Generate refresh token
refresh = str(RefreshToken.for_user(user))

factory = APIRequestFactory()
request = factory.post('/api/users/logout/', {'refresh': refresh}, format='json')
request.user = user

force_authenticate(request, user=user)
view = LogoutView.as_view()
response = view(request)
print('Logout view response status:', response.status_code)
try:
    print('Response data:', response.data)
except Exception:
    pass

from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

outstanding = OutstandingToken.objects.filter(user=user).first()
print('Outstanding token exists:', bool(outstanding))
if outstanding:
    blacklisted = BlacklistedToken.objects.filter(token=outstanding).exists()
    print('Blacklisted:', blacklisted)
else:
    print('No OutstandingToken record found for the refresh string (it may be stored hashed).')
