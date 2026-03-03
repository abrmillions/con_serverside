from rest_framework import serializers
from .models import Application, ApplicationLog
import json


class ApplicationLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.ReadOnlyField(source='actor.get_full_name')
    actor_email = serializers.ReadOnlyField(source='actor.email')

    class Meta:
        model = ApplicationLog
        fields = ['id', 'actor', 'actor_name', 'actor_email', 'action', 'details', 'timestamp']


class ApplicationSerializer(serializers.ModelSerializer):
    applicant = serializers.ReadOnlyField(source="applicant.email")
    previous_license_id = serializers.ReadOnlyField(source="previous_license.id")
    data = serializers.JSONField(required=False, allow_null=True)
    profile_photo = serializers.ImageField(required=False, allow_null=True)
    professional_photo = serializers.ImageField(required=False, allow_null=True)
    company_representative_photo = serializers.ImageField(required=False, allow_null=True)
    logs = ApplicationLogSerializer(many=True, read_only=True)

    class Meta:
        model = Application
        fields = (
            "id",
            "applicant",
            "license_type",
            "subtype",
            "data",
            "status",
            "profile_photo",
            "professional_photo",
            "company_representative_photo",
            "created_at",
            "updated_at",
            "logs",
            "is_renewal",
            "previous_license_id",
        )
        read_only_fields = ("id", "applicant", "created_at", "updated_at")

    def to_internal_value(self, data):
        try:
            d = dict(data)
            if "data" in d:
                val = d["data"]
                if isinstance(val, (list, tuple)) and val:
                    val = val[0]
                if isinstance(val, str):
                    try:
                        d["data"] = json.loads(val)
                    except Exception:
                        d["data"] = val
            return super().to_internal_value(d)
        except Exception:
            return super().to_internal_value(data)

    def validate(self, attrs):
        request = self.context.get("request")
        method = getattr(request, "method", None) if request else None
        license_type = attrs.get("license_type") or (self.instance.license_type if self.instance else None)
        mapping = {
            "profile_photo": "profile_photo",
            "professional_photo": "professional_photo",
            "company_representative_photo": "company_representative_photo",
        }
        required_field = mapping.get(license_type)
        if required_field:
            provided = attrs.get(required_field) or (self.instance and getattr(self.instance, required_field))
            if not provided:
                if method in ("PUT", "PATCH"):
                    raise serializers.ValidationError({required_field: "This photo is required for the selected license type."})

        # Reject non-image uploads (ImageField handles basic validation but be explicit)
        for fld in ("profile_photo", "professional_photo", "company_representative_photo"):
            fval = attrs.get(fld)
            if fval is not None and hasattr(fval, "content_type"):
                if not fval.content_type.startswith("image/"):
                    raise serializers.ValidationError({fld: "Uploaded file must be an image."})

        return super().validate(attrs)
