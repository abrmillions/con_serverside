from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.core.signing import TimestampSigner

from ..models import License


User = get_user_model()


class QRTokenTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', email='tester@example.com', password='pass')
        today = timezone.now().date()
        self.license = License.objects.create(
            owner=self.user,
            license_type='contractor',
            license_number='LIC-TEST-001',
            status='active',
            issued_date=today,
            expiry_date=today + timedelta(days=365),
        )

    def test_token_generation_and_verification(self):
        signer = TimestampSigner()
        token = signer.sign(self.license.license_number)

        resp = self.client.get('/api/licenses/verify/', {'token': token})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('valid'))
        self.assertEqual(data.get('license_number'), self.license.license_number)

    def test_invalid_token(self):
        signer = TimestampSigner()
        token = signer.sign(self.license.license_number)
        bad = token + 'x'

        resp = self.client.get('/api/licenses/verify/', {'token': bad})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data.get('valid'))

    @override_settings(QR_TOKEN_MAX_AGE_SECONDS=0)
    def test_expired_token(self):
        signer = TimestampSigner()
        token = signer.sign(self.license.license_number)

        resp = self.client.get('/api/licenses/verify/', {'token': token})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data.get('valid'))

    def test_generate_qr_requires_auth_and_saves_token(self):
        # unauthenticated should fail
        resp = self.client.post('/api/licenses/qr/', {'license_id': str(self.license.id), 'frontend_url': 'http://localhost:3000'})
        self.assertIn(resp.status_code, (401, 403))

        # authenticate and call
        self.client.force_login(self.user)
        resp2 = self.client.post('/api/licenses/qr/', {'license_id': str(self.license.id), 'frontend_url': 'http://localhost:3000'})
        self.assertEqual(resp2.status_code, 200)
        data = resp2.json()
        self.assertTrue(data.get('qr_code_data'))
        self.license.refresh_from_db()
        self.assertTrue(self.license.qr_code_data and 'token=' in self.license.qr_code_data)
