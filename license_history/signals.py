from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from licenses.models import License
from .models import LicenseStatusHistory


@receiver(pre_save, sender=License)
def capture_old_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._old_status = None
    else:
        try:
            old = License.objects.get(pk=instance.pk)
            instance._old_status = old.status
        except License.DoesNotExist:
            instance._old_status = None


@receiver(post_save, sender=License)
def record_status_change(sender, instance, created, **kwargs):
    old = getattr(instance, "_old_status", None)
    new = instance.status
    if created:
        LicenseStatusHistory.objects.create(
            license=instance,
            old_status="",
            new_status=new or "",
            changed_by=None,
            reason="created",
        )
        return
    if old is not None and old != new:
        LicenseStatusHistory.objects.create(
            license=instance,
            old_status=old or "",
            new_status=new or "",
            changed_by=None,
            reason="status_changed",
        )
