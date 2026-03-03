import os
import sys
import json
import django
from urllib import request as urlreq
from urllib import parse as urlparse

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

BASE = "http://127.0.0.1:8000"
EMAIL = "marchoflink3657@gmail.com"
PASSWORD = "12345678"


def ensure_user(email: str, password: str):
    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if not user:
        user = User.objects.create_user(email=email, username=email.split("@")[0], password=password)
    # Elevate to staff for approval step
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    return user


def api_json(method: str, path: str, headers=None, body=None):
    url = f"{BASE}{path}"
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urlreq.Request(url, method=method.upper())
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urlreq.urlopen(req, data=data, timeout=10) as resp:
            txt = resp.read().decode("utf-8")
            return resp.getcode(), json.loads(txt)
    except Exception as e:
        raise RuntimeError(f"{method} {path} failed: {e}")


def run():
    user = ensure_user(EMAIL, PASSWORD)
    print("User ready:", user.email, "is_staff:", user.is_staff)

    status, tokens = api_json("POST", "/api/users/token/", body={"email": EMAIL, "password": PASSWORD})
    assert status == 200 and "access" in tokens, "login failed"
    access = tokens["access"]
    headers = {"Authorization": f"Bearer {access}"}

    create_body = {
        "main_contractor": {
            "name": "Alpha Builders",
            "registration_number": "REG-ALPHA-001",
            "license_number": "LIC-ALPHA-001",
            "country": "AE",
        },
        "partner_company": {
            "name": "Beta Partners",
            "registration_number": "REG-BETA-002",
            "license_number": "LIC-BETA-002",
            "country": "AE",
        },
        "partnership_type": "joint_venture",
        "ownership_ratio_main": 60,
        "ownership_ratio_partner": 40,
        "start_date": "2026-02-01",
        "end_date": "2026-12-31",
    }
    status, created = api_json("POST", "/api/partnerships/create/", headers=headers, body=create_body)
    assert status in (200, 201), f"create returned {status}"
    pid = created["id"]
    print("Created partnership:", pid, "status:", created["status"])

    status, confirmed = api_json("POST", f"/api/partnerships/{pid}/confirm/", headers=headers, body={"action": "accept"})
    assert status == 200, f"confirm returned {status}"
    print("Confirm status:", confirmed["status"])

    status, approved = api_json("POST", f"/api/partnerships/{pid}/approve/", headers=headers)
    assert status == 200, f"approve returned {status}"
    print("Approved status:", approved["status"])
    print("QR code path:", approved.get("qr_code"))

    status, verify = api_json("GET", f"/api/partnerships/verify/{pid}/")
    print("Verify:", status, verify)


if __name__ == "__main__":
    run()
