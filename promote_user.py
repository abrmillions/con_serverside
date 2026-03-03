import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

def promote_user(email):
    try:
        user = User.objects.get(email=email)
        user.is_staff = True
        user.is_superuser = True  # Optional: gives full permissions
        user.save()
        print(f"Successfully promoted {email} to Admin (Staff & Superuser).")
    except User.DoesNotExist:
        print(f"Error: User with email '{email}' not found.")
        print("Available users:")
        for u in User.objects.all():
            print(f"- {u.email}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python promote_user.py <email>")
        print("\nExisting users:")
        for u in User.objects.all():
            print(f"- {u.email} {'(Admin)' if u.is_staff else ''}")
    else:
        promote_user(sys.argv[1])
