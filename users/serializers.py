from django.contrib.auth import get_user_model
from rest_framework import serializers


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    licenses_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "email", "password", "first_name", "last_name", "phone", "profile_photo", "is_staff", "is_active", "email_verified", "date_joined", "licenses_count")
        read_only_fields = ("is_staff", "date_joined", "licenses_count")
        extra_kwargs = {
            "profile_photo": {"required": False},
            "phone": {"required": False}
        }

    def get_licenses_count(self, obj):
        # Check if licenses app is installed and linked
        if hasattr(obj, 'licenses'):
            return obj.licenses.count()
        return 0

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user
