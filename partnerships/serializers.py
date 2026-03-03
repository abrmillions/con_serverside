from rest_framework import serializers
from .models import Partnership, PartnershipDocument, PartnershipApprovalLog, Company


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ("id", "name", "registration_number", "license_number", "license_expiry_date", "country", "status")
        read_only_fields = ("id",)


class PartnershipDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnershipDocument
        fields = ("id", "document_type", "file", "uploaded_at")
        read_only_fields = ("id", "uploaded_at")


class PartnershipApprovalLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = PartnershipApprovalLog
        fields = ("id", "action", "actor", "actor_name", "actor_role", "actor_identifier", "timestamp")
        read_only_fields = ("id", "timestamp")

    def get_actor_name(self, obj):
        try:
            return getattr(obj.actor, "email", getattr(obj.actor, "username", None))
        except Exception:
            return None


class PartnershipSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source="owner.id")
    main_contractor = CompanySerializer()
    partner_company = CompanySerializer()
    documents = PartnershipDocumentSerializer(many=True, required=False)
    approval_logs = PartnershipApprovalLogSerializer(many=True, required=False)
    registration_data = serializers.JSONField(required=False)
    partners_data = serializers.JSONField(required=False)

    class Meta:
        model = Partnership
        fields = (
            "id",
            "owner",
            "main_contractor",
            "partner_company",
            "partnership_type",
            "ownership_ratio_main",
            "ownership_ratio_partner",
            "status",
            "start_date",
            "end_date",
            "qr_code",
            "certificate_number",
            "created_at",
            "updated_at",
            "documents",
            "approval_logs",
            "registration_data",
            "partners_data",
        )
        read_only_fields = ("id", "owner", "qr_code", "certificate_number", "created_at", "updated_at", "documents", "approval_logs")

    def create(self, validated_data):
        mc_data = validated_data.pop("main_contractor")
        pc_data = validated_data.pop("partner_company")
        docs_data = validated_data.pop("documents", [])
        mc, _ = Company.objects.get_or_create(
            name=mc_data.get("name"),
            defaults=mc_data,
        )
        pc, _ = Company.objects.get_or_create(
            name=pc_data.get("name"),
            defaults=pc_data,
        )
        partnership = Partnership.objects.create(main_contractor=mc, partner_company=pc, **validated_data)
        for d in docs_data:
            PartnershipDocument.objects.create(partnership=partnership, **d)
        return partnership
