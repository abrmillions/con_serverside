from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from vehicles.models import Vehicle
from documents.models import Document
import json


class Command(BaseCommand):
    help = "Create a demo vehicle and attach documents for the given user email"

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="User email")
        parser.add_argument("--password", required=False, help="Set password if creating user")

    def handle(self, *args, **options):
        User = get_user_model()
        email = options["email"].strip().lower()
        password = options.get("password")

        user, created = User.objects.get_or_create(email=email, defaults={"username": email.split("@")[0]})
        if created and password:
            user.set_password(password)
            user.save()
        self.stdout.write(self.style.SUCCESS(f"Using user: {email} (created={created})"))

        data = {
            "vehicleType": "bulldozer",
            "manufacturer": "Caterpillar",
            "model": "D6",
            "year": 2018,
            "plateNumber": "ABC-20258",
            "registrationNumber": "REG-123456",
            "engineNumber": "ENG-987654",
            "chassisNumber": "Y84848Y889899I",
            "ownerName": "Demo Owner",
            "ownerLicense": "LIC-2025-6748",
            "tinNumber": "TIN-123456",
            "address": "Addis Ababa",
        }

        base_plate = data["plateNumber"]
        base_chassis = data["chassisNumber"]
        suffix = 1
        while Vehicle.objects.filter(plate_number=base_plate).exists():
            suffix += 1
            data["plateNumber"] = f"{base_plate}-{suffix}"
        while Vehicle.objects.filter(chassis_number=base_chassis).exists():
            suffix += 1
            data["chassisNumber"] = f"{base_chassis}-{suffix}"

        v = Vehicle.objects.create(owner=user, status="pending", data=data)
        self.stdout.write(self.style.SUCCESS(f"Created vehicle id={v.id}"))

        # Attach four documents
        docs = {
            "registration": "Vehicle Registration Certificate",
            "insurance": "Insurance Certificate",
            "inspection": "Safety Inspection Certificate",
            "ownership": "Proof of Ownership",
        }
        for key, label in docs.items():
            content = ContentFile(f"{label} for vehicle {v.id}".encode("utf-8"))
            filename = f"{key}-{v.id}.txt"
            d = Document.objects.create(uploader=user, name=label, vehicle=v)
            d.file.save(filename, content, save=True)
            self.stdout.write(self.style.SUCCESS(f"Attached document: {label}"))

        # Ensure normalized fields populated
        v.save()
        self.stdout.write(self.style.SUCCESS("Vehicle normalized fields updated from JSON data"))

        self.stdout.write(self.style.SUCCESS("Done. Check admin: vehicles → this vehicle shows docs and fields."))
