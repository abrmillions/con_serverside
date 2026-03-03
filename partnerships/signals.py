from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Partnership, PartnershipApprovalLog

@receiver(pre_save, sender=Partnership)
def partnership_pre_save(sender, instance: Partnership, **kwargs):
    try:
        if instance.end_date and instance.end_date < timezone.localdate():
            if instance.status in {"approved", "active"}:
                instance.status = "expired"
    except Exception:
        pass

@receiver(post_save, sender=Partnership)
def partnership_post_save(sender, instance: Partnership, created, **kwargs):
    try:
        # Simple notification stub
        if instance.status == "expired":
            print(f"[notify] Partnership {instance.id} expired")
    except Exception:
        pass
