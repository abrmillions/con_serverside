from rest_framework import serializers
from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    payer = serializers.ReadOnlyField(source="payer.username")

    class Meta:
        model = Payment
        fields = ("id", "payer", "amount", "currency", "status", "metadata", "created_at")
        read_only_fields = ("id", "payer", "created_at")
