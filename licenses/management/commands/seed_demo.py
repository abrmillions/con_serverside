from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date
from licenses.models import License
from companies.models import Company


class Command(BaseCommand):
    help = "Seed demo users, company, and licenses for quick end-to-end testing"

    def handle(self, *args, **options):
        User = get_user_model()

        # Create demo user
        email = "demo.user@example.com"
        password = "Demo12345!"
        user, created = User.objects.get_or_create(email=email, defaults={
            "username": email,
            "first_name": "Demo",
            "last_name": "User",
        })
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created demo user: {email} / {password}"))
        else:
            self.stdout.write(self.style.WARNING(f"Demo user exists: {email}"))

        # Create company
        company, c_created = Company.objects.get_or_create(
            name="Demo Construction Ltd",
            defaults={
                "registration_number": "DEMO-REG-0001",
                "address": "123 Demo Street",
                "city": "Demo City",
                "state": "DE",
                "zip_code": "00001",
                "phone": "+1 555 000 0001",
                "email": "contact@demo-construction.example.com",
                "website": "https://demo-construction.example.com",
                "contact_person": user,
            },
        )
        if c_created:
            self.stdout.write(self.style.SUCCESS("Created demo company"))
        else:
            self.stdout.write(self.style.WARNING("Demo company exists"))

        # Helper to generate unique license numbers (simple, avoids importing internal helper)
        def gen_license_number():
            prefix = "LIC"
            y = date.today().year
            seq = License.objects.count() + 1
            while True:
                cand = f"{prefix}-{y:04d}-{seq:06d}"
                if not License.objects.filter(license_number=cand).exists():
                    return cand
                seq += 1

        # Contractor License for demo user
        if not License.objects.filter(owner=user, license_type="Contractor License").exists():
            ln = gen_license_number()
            issued = date.today()
            expiry = date(issued.year + 5, issued.month, issued.day)
            lic = License.objects.create(
                owner=user,
                license_type="Contractor License",
                license_number=ln,
                issued_date=issued,
                expiry_date=expiry,
                status="active",
                company=company,
                data={
                    "companyName": company.name,
                    "registrationNumber": company.registration_number,
                    "licenseNumber": ln,
                    "issueDate": issued.isoformat(),
                    "expiryDate": expiry.isoformat(),
                    "subtype": "company_new",
                    "category": "Grade 2 - Medium Projects",
                },
            )
            self.stdout.write(self.style.SUCCESS(f"Issued contractor license {lic.license_number}"))
        else:
            self.stdout.write(self.style.WARNING("Contractor license already exists for demo user"))

        # Professional License for demo user
        if not License.objects.filter(owner=user, license_type="Professional License").exists():
            ln = gen_license_number()
            issued = date.today()
            expiry = date(issued.year + 5, issued.month, issued.day)
            lic = License.objects.create(
                owner=user,
                license_type="Professional License",
                license_number=ln,
                issued_date=issued,
                expiry_date=expiry,
                status="active",
                data={
                    "holderName": f"{user.first_name} {user.last_name}".strip() or email,
                    "licenseNumber": ln,
                    "issueDate": issued.isoformat(),
                    "expiryDate": expiry.isoformat(),
                    "subtype": "professional_new",
                    "level": "Associate",
                },
            )
            self.stdout.write(self.style.SUCCESS(f"Issued professional license {lic.license_number}"))
        else:
            self.stdout.write(self.style.WARNING("Professional license already exists for demo user"))

        self.stdout.write(self.style.SUCCESS("Demo data ready. You can sign in with the demo user to test flows."))

