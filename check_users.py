import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_project.settings')
django.setup()

from users.models import CustomUser
null_count = CustomUser.objects.filter(email__isnull=True).count()
empty_count = CustomUser.objects.filter(email="").count()
print(f"Null emails: {null_count}")
print(f"Empty string emails: {empty_count}")
for u in CustomUser.objects.all():
    if not u.email:
        print(f"ID: {u.id}, Username: {u.username}, Email: '{u.email}'")
