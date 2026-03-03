from rest_framework import serializers
from .models import Vehicle


class VehicleSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source="owner.username")
    registeredAt = serializers.DateTimeField(source="registered_at", read_only=True)
    plateNumber = serializers.CharField(source="plate_number", required=False, allow_blank=True, allow_null=True)
    chassisNumber = serializers.CharField(source="chassis_number", required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Vehicle
        fields = ("id", "owner", "status", "data", "registeredAt", "vin", "make", "model", "year", "plateNumber", "chassisNumber")
        read_only_fields = ("id", "owner", "registeredAt")

    def create(self, validated_data):
        data = validated_data.get("data") or {}
        if isinstance(data, dict):
            validated_data["plate_number"] = validated_data.get("plate_number") or data.get("plateNumber")
            validated_data["chassis_number"] = validated_data.get("chassis_number") or data.get("chassisNumber")
            validated_data["vin"] = validated_data.get("vin") or data.get("vin") or data.get("engineNumber")
            validated_data["make"] = validated_data.get("make") or data.get("manufacturer")
            validated_data["model"] = validated_data.get("model") or data.get("model")
            yr = validated_data.get("year") or data.get("year")
            if yr is not None:
                try:
                    validated_data["year"] = int(yr)
                except Exception:
                    pass
        return super().create(validated_data)

    def update(self, instance, validated_data):
        data = validated_data.get("data")
        if isinstance(data, dict):
            pn = validated_data.get("plate_number") or data.get("plateNumber")
            cn = validated_data.get("chassis_number") or data.get("chassisNumber")
            if pn is not None:
                validated_data["plate_number"] = pn
            if cn is not None:
                validated_data["chassis_number"] = cn
            vin = validated_data.get("vin") or data.get("vin") or data.get("engineNumber")
            make = validated_data.get("make") or data.get("manufacturer")
            model = validated_data.get("model") or data.get("model")
            yr = validated_data.get("year") or data.get("year")
            if vin is not None:
                validated_data["vin"] = vin
            if make is not None:
                validated_data["make"] = make
            if model is not None:
                validated_data["model"] = model
            if yr is not None:
                try:
                    validated_data["year"] = int(yr)
                except Exception:
                    pass
        return super().update(instance, validated_data)
