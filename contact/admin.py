from django.contrib import admin, messages
from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils import timezone
from django.template.loader import render_to_string
from .models import ContactMessage, ContactReply
from systemsettings.models import SystemSettings


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

            if getattr(settings_obj, "email_debug_mode", False):
                print("\n" + "="*50)
                print("DEBUG EMAIL (Contact Reply)")
                print(f"To: {obj.message.email}")
                print(f"Subject: Reply to your message: {obj.message.subject or 'No subject'}")
                print(f"Body:\n{obj.text.strip()}")
                print("="*50 + "\n")
                messages.info(request, "Debug Mode: Email printed to console instead of sending.")
                obj.send_status = "success"
                obj.sent_at = timezone.now()
                obj.save(update_fields=["send_status", "sent_at"])
                return

            from_email = getattr(settings_obj, "support_email", "")

            if not (from_email and obj.message and obj.message.email):
                messages.warning(request, "Reply saved but email not sent due to missing SMTP configuration or recipient email.")
                obj.send_status = "warning"
                obj.sent_at = timezone.now()
                obj.send_error = "Missing SMTP config or recipient"
                obj.save(update_fields=["send_status", "sent_at", "send_error"])
                return

            subject = f"Reply to your message: {obj.message.subject or 'No subject'}"
            admin_name = getattr(getattr(request, "user", None), "get_full_name", lambda: "")() or getattr(request.user, "email", "") or "Admin"
            
            html_body = render_to_string(
                "email/contact_reply.html",
                {
                    "name": obj.message.name,
                    "text": obj.text.strip(),
                    "admin_name": admin_name,
                    "system_name": getattr(settings_obj, "system_name", "Construction License Management System"),
                },
            )
            text_body = (
                f"Hello {obj.message.name},\n\n"
                f"Our team has replied to your message:\n\n"
                f"{obj.text.strip()}\n\n"
                f"— {admin_name}\n"
                f"{getattr(settings_obj, 'system_name', 'Construction License Management System')}"
            )
            
            try:
                connection = get_connection(
                    backend='django.core.mail.backends.smtp.EmailBackend',
                    host=settings_obj.smtp_host,
                    port=settings_obj.smtp_port,
                    username=settings_obj.smtp_user,
                    password=settings_obj.smtp_password,
                    use_tls=settings_obj.smtp_use_tls,
                    use_ssl=getattr(settings_obj, 'smtp_use_ssl', False),
                    timeout=getattr(settings_obj, 'smtp_timeout', 10)
                )
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=text_body,
                    from_email=from_email,
                    to=[obj.message.email],
                    connection=connection
                )
                email.attach_alternative(html_body, "text/html")
                email.send(fail_silently=False)
                messages.success(request, f"Reply saved and email sent to {obj.message.email} via SMTP.")
                obj.send_status = "success"
                obj.send_error = ""
                obj.sent_at = timezone.now()
                obj.save(update_fields=["send_status", "sent_at", "send_error"])
            except Exception as e:
                messages.error(request, f"Failed to send email: {e}")
                obj.send_status = "error"
                obj.send_error = str(e)
                obj.sent_at = timezone.now()
                obj.save(update_fields=["send_status", "sent_at", "send_error"])
        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {e}")
            obj.send_status = "error"
            obj.sent_at = timezone.now()
            obj.send_error = str(e)
            obj.save(update_fields=["send_status", "sent_at", "send_error"])
