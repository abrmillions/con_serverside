from rest_framework import serializers
from .models import Document
from vehicles.models import Vehicle


class DocumentSerializer(serializers.ModelSerializer):
    uploader = serializers.ReadOnlyField(source="uploader.email")
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Document
        fields = ("id", "uploader", "file", "name", "uploaded_at", "verification_status", "verification_score", "verification_details", "verified_at", "application", "vehicle")
        read_only_fields = ("id", "uploader", "uploaded_at")
