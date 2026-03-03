from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model


class VehicleTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="vehuser@example.com", username="vehuser", password="pass1234")
        r = self.client.post("/api/users/token/", {"email": "vehuser@example.com", "password": "pass1234"}, format="json")
        self.token = r.data.get("access")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_create_vehicle(self):
        data = {"vin": "1HGCM82633A004352", "make": "Honda", "model": "Civic", "year": 2020}
        r = self.client.post("/api/vehicles/", data, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["vin"], "1HGCM82633A004352")
