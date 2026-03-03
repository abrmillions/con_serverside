from django.contrib import admin, messages
from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils import timezone
from django.template.loader import render_to_string
from .models import ContactMessage, ContactReply
from systemsettings.models import SystemSettings
from systemsettings.gmail_oauth import send_with_gmail_oauth


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "subject", "status", "created_at")
    search_fields = ("email", "subject", "message")
    list_filter = ("status", "created_at")


@admin.register(ContactReply)
class ContactReplyAdmin(admin.ModelAdmin):
    list_display = ("id", "message", "sender_type", "send_status", "sent_at", "created_at")
    search_fields = ("text",)
    list_filter = ("sender_type", "created_at")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            if change:
                return
            settings_obj = SystemSettings.get_solo()
            if not getattr(settings_obj, "email_notifications", True):
                messages.info(request, "Reply saved. Email notifications are disabled.")
                obj.send_status = "warning"
                obj.sent_at = timezone.now()
                obj.save(update_fields=["send_status", "sent_at"])
                return
            host = getattr(settings_obj, "smtp_host", "") or ""
            port = int(getattr(settings_obj, "smtp_port", 587) or 587)
            user = getattr(settings_obj, "smtp_user", "") or ""
            password = getattr(settings_obj, "smtp_password", "") or ""
            use_tls = bool(getattr(settings_obj, "use_tls", True))
            if not (host and user and obj.message and obj.message.email):
                messages.warning(request, "Reply saved but email not sent due to missing SMTP configuration or recipient email.")
                obj.send_status = "warning"
                obj.sent_at = timezone.now()
                obj.send_error = "Missing SMTP config or recipient"
                obj.save(update_fields=["send_status", "sent_at", "send_error"])
                return
            connection = get_connection(
                host=host,
                port=port,
                username=user,
                password=password,
                use_tls=use_tls,
            )
            subject = f"Reply to your message: {obj.message.subject or 'No subject'}"
            admin_name = getattr(getattr(request, "user", None), "get_full_name", lambda: "")() or getattr(request.user, "email", "") or "Admin"
            body = (
                f"Hello {obj.message.name},\n\n"
                f"Our team has replied to your message:\n\n"
                f"{obj.text.strip()}\n\n"
                f"— {admin_name}\n"
                f"{getattr(settings_obj, 'system_name', 'Construction License Management System')}"
            )
            html_body = render_to_string(
                "email/contact_reply.html",
                {
                    "name": obj.message.name,
                    "text": obj.text.strip(),
                    "admin_name": admin_name,
                    "system_name": getattr(settings_obj, "system_name", "Construction License Management System"),
                },
            )
            email = EmailMultiAlternatives(
                subject=subject,
                body=body,
                from_email=user,
                to=[obj.message.email],
                reply_to=[getattr(settings_obj, "support_email", user) or user],
                connection=connection,
            )
            email.attach_alternative(html_body, "text/html")
            try:
                if getattr(settings_obj, "use_gmail_oauth", False):
                    msg_obj = email.message()
                    send_with_gmail_oauth(
                        from_email=user,
                        to_emails=[obj.message.email],
                        message_str=msg_obj.as_string(),
                        client_id=getattr(settings_obj, "gmail_client_id", ""),
                        client_secret=getattr(settings_obj, "gmail_client_secret", ""),
                        refresh_token=getattr(settings_obj, "gmail_refresh_token", ""),
                    )
                    messages.success(request, f"Reply saved and email sent to {obj.message.email} via Gmail OAuth.")
                    obj.send_status = "success"
                    obj.sent_at = timezone.now()
                    obj.send_error = ""
                    obj.save(update_fields=["send_status", "sent_at", "send_error"])
                else:
                    sent_count = email.send(fail_silently=False)
                    if sent_count > 0:
                        messages.success(request, f"Reply saved and email sent to {obj.message.email}.")
                        obj.send_status = "success"
                        obj.sent_at = timezone.now()
                        obj.send_error = ""
                        obj.save(update_fields=["send_status", "sent_at", "send_error"])
                    else:
                        messages.warning(request, "Reply saved but email not sent (no recipients accepted).")
                        obj.send_status = "warning"
                        obj.sent_at = timezone.now()
                        obj.send_error = "No recipients accepted"
                        obj.save(update_fields=["send_status", "sent_at", "send_error"])
            except Exception as e:
                messages.error(request, f"Reply saved but email failed to send: {e}")
                obj.send_status = "error"
                obj.sent_at = timezone.now()
                obj.send_error = str(e)
                obj.save(update_fields=["send_status", "sent_at", "send_error"])
        except Exception as e:
            messages.error(request, f"Reply saved but email failed to send: {e}")
            obj.send_status = "error"
            obj.sent_at = timezone.now()
            obj.send_error = str(e)
            obj.save(update_fields=["send_status", "sent_at", "send_error"])
