from django.contrib.auth import get_user_model, password_validation
from rest_framework import serializers
from systemsettings.models import SystemSettings


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    password_confirm = serializers.CharField(write_only=True, required=False)
    licenses_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = User
        fields = (
            "id", "username", "email", "password", "password_confirm",
            "first_name", "last_name", "phone", "profile_photo",
            "is_staff", "is_active", "email_verified", "date_joined", "licenses_count", "role"
        )
        read_only_fields = ("date_joined", "licenses_count")
        extra_kwargs = {
            "profile_photo": {"required": False},
            "phone": {"required": False}
        }

    def validate(self, data):
        password = data.get('password')
        password_confirm = data.get('password_confirm')
        
        if password and password_confirm:
            if password != password_confirm:
                raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
            
            # Use dynamic minimum length from system settings
            try:
                settings_obj = SystemSettings.get_solo()
                min_len = settings_obj.password_min_length
                if len(password) < min_len:
                    raise serializers.ValidationError({"password": f"Password must be at least {min_len} characters long."})
            except Exception:
                pass

            # Use Django's password validation
            try:
                # Need to provide user instance if updating
                if self.instance:
                    user = self.instance
                else:
                    # Create a dummy user for validation purposes, removing non-model fields
                    # Filter for concrete fields to be safe
                    concrete_field_names = {f.name for f in User._meta.concrete_fields}
                    validation_data = {k: v for k, v in data.items() if k in concrete_field_names}
                    user = User(**validation_data)
                
                password_validation.validate_password(password, user=user)
            except Exception as e:
                # Handle both Django ValidationError (has .messages) and other exceptions
                error_msg = list(e.messages) if hasattr(e, 'messages') else [str(e)]
                raise serializers.ValidationError({"password": error_msg})
                
        return data

    def get_licenses_count(self, obj):
        # Check if licenses app is installed and linked
        if hasattr(obj, 'licenses'):
            return obj.licenses.count()
        return 0

    def create(self, validated_data):
        # Pop non-model fields
        password = validated_data.pop("password", None)
        validated_data.pop("password_confirm", None)
        validated_data.pop("licenses_count", None)
        
        # Filter for concrete fields to be extra safe
        concrete_field_names = {f.name for f in User._meta.concrete_fields}
        model_data = {k: v for k, v in validated_data.items() if k in concrete_field_names}
        
        # Use create_user to handle password hashing and internal signals
        user = User.objects.create_user(password=password, **model_data)
        return user
