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
        fields = ("id", "document_type", "file", "uploaded_at", "verification_status", "verification_score", "verification_details", "verified_at")
        read_only_fields = ("id", "uploaded_at", "verification_status", "verification_score", "verification_details", "verified_at")


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
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
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
        request = self.context.get("request")
        owner = validated_data.pop("owner", request.user if request else None)
        
        mc_data = validated_data.pop("main_contractor")
        pc_data = validated_data.pop("partner_company")
        docs_data = validated_data.pop("documents", [])
        
        # Use only valid Company fields for get_or_create
        company_fields = ["name", "registration_number", "license_number", "license_expiry_date", "country", "status"]
        
        def clean_company_data(data):
            return {k: v for k, v in data.items() if k in company_fields}

        mc_clean = clean_company_data(mc_data)
        pc_clean = clean_company_data(pc_data)

        mc, _ = Company.objects.get_or_create(
            name=mc_clean.get("name"),
            defaults=mc_clean,
        )
        if owner and not mc.owner:
            try:
                mc.owner = owner
                mc.save()
            except Exception:
                pass

        pc, _ = Company.objects.get_or_create(
            name=pc_clean.get("name"),
            defaults=pc_clean,
        )
        if owner and not pc.owner:
            try:
                pc.owner = owner
                pc.save()
            except Exception:
                pass
        
        partnership = Partnership.objects.create(
            owner=owner,
            main_contractor=mc, 
            partner_company=pc, 
            **validated_data
        )
        
        for d in docs_data:
            PartnershipDocument.objects.create(partnership=partnership, **d)
            
        return partnership
