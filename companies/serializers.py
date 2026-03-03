from rest_framework import serializers
from .models import Company


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = (
            "id",
            "name",
            "registration_number",
            "address",
            "city",
            "state",
            "zip_code",
            "contact_person",
            "phone",
            "email",
            "website",
            "registration_date",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "registration_date", "created_at", "updated_at")
