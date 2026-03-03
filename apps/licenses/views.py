from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from .models import License
from rest_framework import serializers


class LicenseSerializer(serializers.ModelSerializer):
    user_email = serializers.ReadOnlyField(source='user.email')
    issued_by_email = serializers.ReadOnlyField(source='issued_by.email')
    application_id = serializers.ReadOnlyField(source='application.id')
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = License
        fields = '__all__'
        read_only_fields = ['id', 'user', 'application', 'issued_by', 'created_at', 'updated_at']


class LicenseVerificationSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    license_number = serializers.CharField(read_only=True)
    holder_name = serializers.CharField(source='user.get_full_name', read_only=True)
    status = serializers.CharField(read_only=True)
    expiry_date = serializers.DateField(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)
    qr_code_data = serializers.CharField(read_only=True)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['is_valid'] = instance.is_active
        if not representation['holder_name']:
            representation['holder_name'] = instance.user.email
        return representation


class LicenseQRGenerationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        license_id = request.data.get('license_id')
        frontend_url = request.data.get('frontend_url', 'http://localhost:3000')

        if not license_id:
            return Response({"detail": "License ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        license = get_object_or_404(License, id=license_id, user=request.user)

        verification_url = f"{frontend_url}/verify?licenseNumber={license.license_number}"

        license.qr_code_data = verification_url
        license.save()

        return Response(
            {
                "success": True,
                "license_id": str(license.id),
                "qr_code_data": license.qr_code_data,
                "message": "QR code data generated and saved."
            },
            status=status.HTTP_200_OK
        )


class LicenseVerificationView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        license_number = request.query_params.get('licenseNumber') or request.query_params.get('license_number')

        if not license_number:
            return Response({"valid": False, "detail": "License number is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            s = str(license_number).strip()
            dash_chars = r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFE58\uFE63\uFF0D]"
            import re
            s_norm = re.sub(dash_chars, "-", s)
            lic = (License.objects.filter(license_number__iexact=s_norm).first())
            if not lic:
                try:
                    lic = (
                        License.objects.filter(
                            models.Q(data__licenseNumber__iexact=s_norm)
                            | models.Q(data__license_number__iexact=s_norm)
                            | models.Q(data__registrationNumber__iexact=s_norm)
                            | models.Q(data__registration_number__iexact=s_norm)
                        ).first()
                    )
                except Exception:
                    lic = None
            if not lic:
                return Response({"valid": False, "detail": "License not found."}, status=status.HTTP_404_NOT_FOUND)
            serializer = LicenseVerificationSerializer(lic)
            data = serializer.data
            st = str(getattr(lic, 'status', '') or '').lower()
            not_expired = True
            try:
                exp = getattr(lic, 'expiry_date', None)
                if exp:
                    from datetime import date
                    not_expired = exp >= date.today()
            except Exception:
                not_expired = True
            data['valid'] = (st in ('approved', 'active')) and not_expired
            return Response(data, status=status.HTTP_200_OK)
        except License.DoesNotExist:
            return Response({"valid": False, "detail": "License not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"valid": False, "detail": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
