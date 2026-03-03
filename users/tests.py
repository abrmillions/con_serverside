from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model


class CheckEmailViewTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="exists@example.com", username="exists", password="pass1234")

    def test_missing_email(self):
        r = self.client.get("/api/users/check-email/")
        self.assertEqual(r.status_code, 400)
        self.assertIn("detail", r.data)

    def test_invalid_syntax(self):
        r = self.client.get("/api/users/check-email/?email=not-an-email")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["syntax_valid"])
        # Domain heuristic will also be false
        self.assertFalse(r.data["domain_likely_valid"])
        self.assertFalse(r.data["exists_in_system"])

    def test_valid_domain_nonexistent(self):
        r = self.client.get("/api/users/check-email/?email=newuser@example.com")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["syntax_valid"])
        self.assertTrue(r.data["domain_likely_valid"])
        self.assertFalse(r.data["exists_in_system"])

    def test_existing_email(self):
        r = self.client.get("/api/users/check-email/?email=exists@example.com")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["syntax_valid"])
        self.assertTrue(r.data["domain_likely_valid"])
        self.assertTrue(r.data["exists_in_system"])


class EmailVerificationFlowTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="verifyme@example.com", username="verifyme", password="pass1234")

    def test_request_and_confirm_verification(self):
        # Request verification
        r = self.client.post("/api/users/email-verification/request/", {"email": "verifyme@example.com"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("verify_url", r.data)

        # Extract uid and token from URL for confirm
        url = r.data["verify_url"]
        # simplistic parse
        import urllib.parse as up
        parsed = up.urlparse(url)
        qs = up.parse_qs(parsed.query)
        uid = qs.get("uid", [""])[0]
        token = qs.get("token", [""])[0]
        self.assertTrue(uid)
        self.assertTrue(token)

        # Confirm
        c = self.client.post(f"/api/users/email-verification/confirm/?uid={uid}&token={token}")
        self.assertEqual(c.status_code, 200)
        # Reload user
        User = get_user_model()
        u = User.objects.get(email="verifyme@example.com")
        self.assertTrue(getattr(u, "email_verified", False))
