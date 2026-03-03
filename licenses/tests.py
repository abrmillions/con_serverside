from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model


class LicenseIntegrationTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="licuser@example.com", username="licuser", password="pass1234")
        r = self.client.post("/api/users/token/", {"email": "licuser@example.com", "password": "pass1234"}, format="json")
        self.token = r.data.get("access")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_endpoints_create_qr_verify_download(self):
        # Create active license via API
        payload = {
            "license_type": "profile",
            "data": {"companyName": "Acme Construction"}
        }
        r = self.client.post("/api/licenses/", payload, format="json")
        self.assertEqual(r.status_code, 201)
        lic = r.data
        self.assertEqual(lic["license_type"], "profile")
        self.assertTrue(lic["status"] in ("active", "approved"))
        self.assertIsNotNone(lic["license_number"])

        # Generate QR data
        qr = self.client.post("/api/licenses/qr/", {"license_id": lic["id"], "frontend_url": "http://localhost:3000"}, format="json")
        self.assertEqual(qr.status_code, 200)
        self.assertTrue(qr.data.get("success"))
        self.assertIn("qr_code_data", qr.data)

        # Verify license by number
        v = self.client.get(f"/api/licenses/verify/?license_number={lic['license_number']}")
        self.assertEqual(v.status_code, 200)
        self.assertTrue(v.data.get("valid"))
        # company_name should be present in verification output if provided in data
        self.assertEqual(v.data.get("company_name"), "Acme Construction")

        # Download license data (owner)
        d = self.client.get(f"/api/licenses/download/{lic['id']}/")
        self.assertEqual(d.status_code, 200)
        self.assertTrue(d.data.get("success"))
        self.assertEqual(d.data["license"]["id"], lic["id"])

    def test_download_forbidden_for_other_user(self):
        # Create license as primary user
        payload = {"license_type": "profile"}
        r = self.client.post("/api/licenses/", payload, format="json")
        self.assertEqual(r.status_code, 201)
        lic = r.data

        # Login as a different user
        User = get_user_model()
        other = User.objects.create_user(email="other@example.com", username="other", password="pass1234")
        r2 = self.client.post("/api/users/token/", {"email": "other@example.com", "password": "pass1234"}, format="json")
        token2 = r2.data.get("access")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token2}")

        d = self.client.get(f"/api/licenses/download/{lic['id']}/")
        self.assertEqual(d.status_code, 403)
        self.assertIn("detail", d.data)
