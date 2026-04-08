from rest_framework import serializers
from .models import ContactMessage, ContactReply


class ContactReplySerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()

    class Meta:
        model = ContactReply
        fields = ("id", "sender_type", "text", "created_at", "sender_name", "send_status", "send_error", "sent_at")
        read_only_fields = ("id", "created_at", "sender_name", "send_status", "send_error", "sent_at")

    def get_sender_name(self, obj):
        if obj.sender:
            return obj.sender.get_full_name() or obj.sender.email
        return "Admin"


class ContactMessageSerializer(serializers.ModelSerializer):
    replies = ContactReplySerializer(many=True, read_only=True)

    class Meta:
        model = ContactMessage
        fields = ("id", "user", "name", "email", "subject", "message", "status", "created_at", "updated_at", "replies")
        read_only_fields = ("id", "user", "created_at", "updated_at", "replies")
