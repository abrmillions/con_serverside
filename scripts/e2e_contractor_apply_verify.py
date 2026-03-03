import os
import sys
import django
from datetime import date
from django.core.files.base import ContentFile
from urllib import request as urlreq, parse as urlparse
import io

# Ensure backend project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Setup Django
try:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
except Exception:
    os.environ["DJANGO_SETTINGS_MODULE"] = "backend_project.settings"
    django.setup()

from django.contrib.auth import get_user_model
from applications.models import Application
from licenses.models import License

EMAIL = "contractor.tester@example.com"
PASSWORD = "TestPass123!"

def ensure_user(email, password):
    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if not user:
        user = User.objects.create_user(email=email, username=email.split("@")[0], password=password)
    # Staff to simplify issuing during test
    user.is_staff = True
    user.is_superuser = True
    user.save()
    return user

def create_contractor_application(user):
    app = Application.objects.create(
        applicant=user,
        license_type="Contractor License",
        data={
            "applicantName": "Contractor Test",
            "email": EMAIL,
            "phone": "0912345678",
            "companyName": "Test Construction PLC",
            "registrationNumber": "REG-TEST-001",
            "workScopes": ["building", "road"],
        },
        subtype="grade-a",
    )
    # Attach a tiny dummy image as profile_photo to satisfy image field
    dummy = io.BytesIO(b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xFF\xFF\xFF\x21\xF9\x04\x01\x00\x00\x00\x00\x2C\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x4C\x01\x00\x3B")
    app.profile_photo.save("contractor_test.gif", ContentFile(dummy.getvalue()), save=True)
    return app

def issue_license_from_application(app, actor):
    today = date.today()
    lic = License.objects.filter(owner=app.applicant, license_type=app.license_type).order_by("-created_at").first()
    if not lic:
        # generate license number LIC-YYYY-XXXXXX
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
        data = {
            "application_id": app.id,
            "subtype": app.subtype,
            "licenseNumber": license_number,
            "issueDate": today.isoformat(),
            "expiryDate": expiry.isoformat(),
            "companyName": app.data.get("companyName"),
        }
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
        # backfill essentials
        lic.data = lic.data or {}
        lic.data.setdefault("application_id", app.id)
        lic.data.setdefault("subtype", app.subtype)
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
    # copy photo
    if app.profile_photo:
        try:
            app.profile_photo.open("rb")
            content = app.profile_photo.read()
            name = os.path.basename(app.profile_photo.name)
            lic.license_photo.save(name, ContentFile(content))
            app.profile_photo.close()
            lic.save(update_fields=["license_photo"])
        except Exception:
            pass
    return lic

def verify_via_api(license_number):
    url = f"http://127.0.0.1:8000/api/licenses/verify?{urlparse.urlencode({'licenseNumber': license_number})}"
    req = urlreq.Request(url, method="GET")
    try:
        with urlreq.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            print("Verification status:", resp.getcode())
            print(body)
            return resp.getcode(), body
    except Exception as e:
        print("Verification request failed:", str(e))
        return 0, str(e)

def run():
    user = ensure_user(EMAIL, PASSWORD)
    app = create_contractor_application(user)
    lic = issue_license_from_application(app, user)
    print("User:", user.email)
    print("Application ID:", app.id)
    print("License ID:", lic.id)
    print("License Number:", lic.license_number)
    print("License Photo:", lic.license_photo.url if lic.license_photo else None)
    status, body = verify_via_api(lic.license_number)
    print("E2E contractor apply+verify complete.")

if __name__ == "__main__":
    run()
