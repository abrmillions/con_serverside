from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model


class PartnershipTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="partuser@example.com", username="partuser", password="pass1234")
        r = self.client.post("/api/users/token/", {"email": "partuser@example.com", "password": "pass1234"}, format="json")
        self.token = r.data.get("access")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_create_partnership(self):
        data = {"name": "BuildCo", "description": "Construction partners", "partners": [{"name": "Alice"}]}
        r = self.client.post("/api/partnerships/", data, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["name"], "BuildCo")
