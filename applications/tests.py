from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from licenses.models import License


class ApplicationFlowSystemTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        # Applicant
        self.applicant = User.objects.create_user(email="applicant@example.com", username="applicant", password="pass1234")
        r = self.client.post("/api/users/token/", {"email": "applicant@example.com", "password": "pass1234"}, format="json")
        self.applicant_token = r.data.get("access")
        # Admin
        self.admin = User.objects.create_user(email="admin@example.com", username="admin", password="pass1234", is_staff=True, is_superuser=True)
        r2 = self.client.post("/api/users/token/", {"email": "admin@example.com", "password": "pass1234"}, format="json")
        self.admin_token = r2.data.get("access")

    def test_application_approval_creates_license_and_verification(self):
        # Applicant creates application
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.applicant_token}")
        app_payload = {
            "license_type": "profile",
            "data": {
                "companyName": "MegaBuild Ltd",
                "subtype": "grade-a"
            }
        }
        ar = self.client.post("/api/applications/", app_payload, format="json")
        self.assertEqual(ar.status_code, 201)
        app_id = ar.data["id"]

        # Admin approves application
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        apr = self.client.post(f"/api/applications/{app_id}/approve/")
        self.assertEqual(apr.status_code, 200)

        # Applicant fetches created license via application endpoint
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.applicant_token}")
        lr = self.client.get(f"/api/applications/{app_id}/license/")
        self.assertEqual(lr.status_code, 200)
        lic = lr.data
        self.assertEqual(lic["license_type"], "profile")
        self.assertIsNotNone(lic["license_number"])
        # Company name should be present in license data
        self.assertEqual(lic["data"].get("companyName"), "MegaBuild Ltd")

        # Verify: pending licenses should return valid False
        vr = self.client.get(f"/api/licenses/verify/?license_number={lic['license_number']}")
        self.assertEqual(vr.status_code, 200)
        self.assertFalse(vr.data.get("valid"))
        self.assertIn("not approved", str(vr.data.get("detail", "")).lower())

        # Owner marks license as approved via PATCH
        pr = self.client.patch(f"/api/licenses/{lic['id']}/", {"status": "approved"}, format="json")
        self.assertIn(pr.status_code, (200, 202))
        # Confirm status changed
        lobj = License.objects.get(pk=lic["id"])
        self.assertEqual(lobj.status, "approved")

        # Verify again: now valid True and company_name present
        vr2 = self.client.get(f"/api/licenses/verify/?license_number={lic['license_number']}")
        self.assertEqual(vr2.status_code, 200)
        self.assertTrue(vr2.data.get("valid"))
        self.assertEqual(vr2.data.get("company_name"), "MegaBuild Ltd")

        # Download should succeed for owner
        dr = self.client.get(f"/api/licenses/download/{lic['id']}/")
        self.assertEqual(dr.status_code, 200)
        self.assertTrue(dr.data.get("success"))
