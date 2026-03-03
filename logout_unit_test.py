import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIRequestFactory
from users.views import LogoutView
from rest_framework.test import force_authenticate

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
force_authenticate(request, user=user)

view = LogoutView.as_view()
response = view(request)
print('Logout view response status:', response.status_code)
try:
    print('Response data:', response.data)
except Exception:
    pass

# Try to reuse the refresh token by creating a new RefreshToken instance
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

outstanding = OutstandingToken.objects.filter(token=refresh).first()
print('Outstanding token exists:', bool(outstanding))
if outstanding:
    blacklisted = BlacklistedToken.objects.filter(token=outstanding).exists()
    print('Blacklisted:', blacklisted)
else:
    print('No OutstandingToken record found for the refresh string (it may be stored hashed).')
