import os
import sys
import django
from datetime import date
from django.core.files.base import ContentFile
from urllib import request as urlreq, parse as urlparse
import json
import io

# Ensure backend project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Setup Django
# Try primary settings module; if it fails, fall back
try:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
except Exception:
    os.environ["DJANGO_SETTINGS_MODULE"] = "backend_project.settings"
django.setup()

from django.contrib.auth import get_user_model
from applications.models import Application
from licenses.models import License

EMAIL = "marchoflink365@gmail.com"
PASSWORD = "12345678"

def ensure_user(email, password):
    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if not user:
        user = User.objects.create_user(email=email, username=email.split("@")[0], password=password)
    # Promote to staff to simplify testing flows
    user.is_staff = True
    user.is_superuser = True
    user.save()
    return user

def create_professional_application(user):
    # Use an existing sample image from media if available
    sample_path = os.path.join("backend", "media", "profile_photos", "test_image.jpg")
    app = Application.objects.create(
        applicant=user,
        license_type="professional",
        subtype="general",
        data={"note": "test-run"},
    )
    if os.path.exists(sample_path):
        with open(sample_path, "rb") as f:
            content = f.read()
        app.professional_photo.save("professional_test.jpg", ContentFile(content), save=True)
    else:
        # Create a small dummy binary to satisfy ImageField in test environments
        dummy = io.BytesIO(b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xFF\xFF\xFF\x21\xF9\x04\x01\x00\x00\x00\x00\x2C\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x4C\x01\x00\x3B")
        app.professional_photo.save("professional_test.gif", ContentFile(dummy.getvalue()), save=True)
    return app

def issue_license_from_application(app, actor):
    today = date.today()
    # Try to find existing license for this user/type
    lic = License.objects.filter(owner=app.applicant, license_type=app.license_type).order_by("-created_at").first()
    if not lic:
        # Generate a unique license number
        prefix = "LIC"
        year = today.year
        seq = License.objects.count() + 1
        while True:
            candidate = f"{prefix}-{year:04d}-{seq:06d}"
            if not License.objects.filter(license_number=candidate).exists():
                license_number = candidate
                break
            seq += 1
        expiry = date(today.year + 5, today.month, today.day)
        data = {"application_id": app.id, "subtype": app.subtype, "licenseNumber": license_number, "issueDate": today.isoformat(), "expiryDate": expiry.isoformat()}
        lic = License.objects.create(
            owner=app.applicant,
            license_type=app.license_type,
            license_number=license_number,
            issued_by=actor,
            issued_date=today,
            expiry_date=expiry,
            data=data,
            status="active",
        )
    else:
        # Ensure application_id and dates exist
        if not lic.data or not isinstance(lic.data, dict):
            lic.data = {}
        lic.data.setdefault("application_id", app.id)
        lic.data.setdefault("subtype", app.subtype)
        # Assign license_number if missing
        if not lic.license_number or str(lic.license_number).strip() == "":
            prefix = "LIC"
            year = today.year
            seq = License.objects.count() + 1
            while True:
                candidate = f"{prefix}-{year:04d}-{seq:06d}"
                if not License.objects.filter(license_number=candidate).exists():
                    lic.license_number = candidate
                    break
                seq += 1
            lic.data["licenseNumber"] = lic.license_number
            lic.data["license_number"] = lic.license_number
        if lic.issued_date is None:
            lic.issued_date = today
        if lic.expiry_date is None:
            lic.expiry_date = date(today.year + 5, today.month, today.day)
        lic.save(update_fields=["data", "issued_date", "expiry_date", "license_number"])
    # Copy photo from application
    candidates = [app.professional_photo, app.profile_photo, app.company_representative_photo]
    photo_field = next((f for f in candidates if f and getattr(f, "name", None)), None)
    if photo_field:
        try:
            photo_field.open("rb")
            try:
                name = os.path.basename(photo_field.name)
                content = photo_field.read()
                lic.license_photo.save(name, ContentFile(content))
            finally:
                try:
                    photo_field.close()
                except Exception:
                    pass
        except Exception:
            try:
                lic.license_photo = photo_field
            except Exception:
                pass
        lic.save(update_fields=["license_photo"])
    return lic

def verify_via_api(license_number):
    url = f"http://127.0.0.1:8000/api/licenses/verify?{urlparse.urlencode({'licenseNumber': license_number})}"
    req = urlreq.Request(url, method="GET")
    try:
        with urlreq.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            print("Verification status:", resp.getcode())
            print(body)
    except Exception as e:
        print("Verification request failed:", str(e))

def run():
    user = ensure_user(EMAIL, PASSWORD)
    app = create_professional_application(user)
    lic = issue_license_from_application(app, user)
    print("User:", user.email)
    print("Application ID:", app.id)
    print("License ID:", lic.id)
    print("License Number:", lic.license_number)
    print("License Photo:", lic.license_photo.url if lic.license_photo else None)
    verify_via_api(lic.license_number)

if __name__ == "__main__":
    run()
