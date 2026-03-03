from django.contrib.auth import get_user_model
from licenses.models import License

EMAIL = 'teme19@gmail.com'

def run():
    User = get_user_model()
    user = User.objects.filter(email=EMAIL).first()
    print('USER:', user)
    if not user:
        print('NO_USER')
        return

    l = License.objects.create(
        owner=user,
        license_type='contractor',
        license_number='LIC-TEST-API-001',
        data={
            'licenseNumber': 'LIC-TEST-API-001',
            'holderName': 'teme19',
            'companyName': 'LocalTestCo',
            'registrationNumber': 'LIC-TEST-API-001',
            'verificationUrl': 'http://localhost:3000/verify/LIC-TEST-API-001',
        },
        status='active'
    )
    print('CREATED', l.id)

if __name__ == '__main__':
    run()
