from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Application
from .notifications import send_application_notification

@receiver(pre_save, sender=Application)
def track_status_change(sender, instance, **kwargs):
    """
    Store the original status of an application before it is saved.
    """
    if instance.pk:
        try:
            old_instance = Application.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Application.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None

@receiver(post_save, sender=Application)
def handle_application_status_change(sender, instance, created, **kwargs):
    """
    Signal to automatically send notifications when an application status changes.
    """
    if created:
        # Send "Received" notification when first created
        send_application_notification(instance, "received")
    else:
        # Check if status has changed
        old_status = getattr(instance, '_old_status', None)
        if old_status and old_status != instance.status:
            # Status has changed!
            send_application_notification(instance, instance.status)
