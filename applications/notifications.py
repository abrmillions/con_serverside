from django.core.mail import send_mail, get_connection
from systemsettings.models import SystemSettings
from .models import Notification
import logging

logger = logging.getLogger(__name__)

def get_dynamic_email_connection(settings):
    """
    Create a Django email connection using SMTP settings from SystemSettings model.
    """
    return get_connection(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        use_tls=settings.smtp_use_tls,
        use_ssl=settings.smtp_use_ssl,
        timeout=settings.smtp_timeout,
    )

def send_application_notification(application, status_name, custom_details=None):
    """
    Send a notification to the applicant about their application status change.
    Respects SystemSettings for email/sms toggles and uses the configured template.
    Automatically fetches the applicant's email.
    """
    settings = SystemSettings.get_solo()
    applicant = application.applicant
    
    print(f"DEBUG: Triggering notification for App {application.id}, Status: {status_name}")
    
    if not applicant or not applicant.email:
        print(f"DEBUG: Notification failed - applicant {applicant} has no email.")
        logger.warning(f"Cannot send notification for application {application.id}: applicant has no email.")
        return False

    # 0. Create in-app notification
    try:
        template = settings.notification_template
        name = getattr(applicant, 'first_name', '') or getattr(applicant, 'username', 'Applicant')
        if not name and hasattr(applicant, 'get_full_name'):
            name = applicant.get_full_name()
            
        body = template.format(
            name=name,
            id=application.id,
            status=status_name,
            license_type=application.license_type
        )
        
        if custom_details:
            body += f"\n\nDetails: {custom_details}"

        subject = f"Application Update: {application.license_type} (#{application.id})"
        
        Notification.objects.create(
            user=applicant,
            application=application,
            title=subject,
            message=body
        )
        print(f"DEBUG: In-app notification created for {applicant.email}")
    except Exception as e:
        print(f"DEBUG: Error creating in-app notification: {str(e)}")
        logger.error(f"Failed to create in-app notification for application {application.id}: {str(e)}")

    # 1. Email Notification
    if settings.email_notifications:
        print(f"DEBUG: Email notifications enabled. Target: {applicant.email}")
        try:
            template = settings.notification_template
            
            # Simple placeholder replacement
            # {name}, {id}, {status}, {license_type}
            name = getattr(applicant, 'first_name', '') or getattr(applicant, 'username', 'Applicant')
            if not name and hasattr(applicant, 'get_full_name'):
                name = applicant.get_full_name()
                
            body = template.format(
                name=name,
                id=application.id,
                status=status_name,
                license_type=application.license_type
            )
            
            if custom_details:
                body += f"\n\nDetails: {custom_details}"

            subject = f"Application Update: {application.license_type} (#{application.id})"
            
            # If debug mode is on, just log it
            if settings.email_debug_mode:
                print(f"DEBUG: Email Debug Mode is ON. Printing to console instead of sending.")
                logger.info(f"EMAIL DEBUG MODE: Sending email to {applicant.email}")
                logger.info(f"Subject: {subject}")
                logger.info(f"Body: {body}")
                # Also print to console as requested by the help_text in models.py
                print(f"\n--- EMAIL DEBUG MODE ---\nTo: {applicant.email}\nSubject: {subject}\nBody:\n{body}\n------------------------\n")
            else:
                if not settings.smtp_host:
                    print("DEBUG: Email failed - SMTP Host not configured in System Settings.")
                    return False
                    
                print(f"DEBUG: Attempting to send email via SMTP ({settings.smtp_host}:{settings.smtp_port})...")
                # Use dynamic connection from database settings
                connection = get_dynamic_email_connection(settings)
                
                send_mail(
                    subject=subject,
                    message=body,
                    from_email=settings.support_email or None,
                    recipient_list=[applicant.email],
                    connection=connection,
                    fail_silently=False,
                )
                print(f"DEBUG: Email successfully sent to {applicant.email}")
                logger.info(f"Notification email sent to {applicant.email} for application {application.id}")
                
        except Exception as e:
            print(f"DEBUG: Email sending error: {str(e)}")
            logger.error(f"Failed to send notification email for application {application.id}: {str(e)}")
    else:
        print("DEBUG: Email notifications are disabled in System Settings.")

    # 2. SMS Notification (Placeholder for future implementation)
    if settings.sms_notifications:
        # Check if applicant has phone
        phone = getattr(applicant, 'phone', None)
        if phone:
            print(f"DEBUG: SMS Notification triggered for {phone} (Logic not implemented)")
            logger.info(f"SMS Notification triggered for {phone} (SMS logic not implemented yet)")
        else:
            print(f"DEBUG: SMS failed - applicant has no phone number.")
            logger.warning(f"SMS notification enabled but applicant {applicant.id} has no phone number.")

    return True
