from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model


class PaymentTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="payuser@example.com", username="payuser", password="pass1234")
        r = self.client.post("/api/users/token/", {"email": "payuser@example.com", "password": "pass1234"}, format="json")
        self.token = r.data.get("access")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_create_payment(self):
        data = {"amount": "150.00", "currency": "USD"}
        r = self.client.post("/api/payments/", data, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["amount"], "150.00")
