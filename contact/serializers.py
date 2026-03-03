from rest_framework import serializers
from .models import ContactMessage, ContactReply


class ContactReplySerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactReply
        fields = ("id", "sender_type", "text", "created_at")
        read_only_fields = ("id", "created_at")


class ContactMessageSerializer(serializers.ModelSerializer):
    replies = ContactReplySerializer(many=True, read_only=True)

    class Meta:
        model = ContactMessage
        fields = ("id", "user", "name", "email", "subject", "message", "status", "created_at", "updated_at", "replies")
        read_only_fields = ("id", "user", "status", "created_at", "updated_at", "replies")
