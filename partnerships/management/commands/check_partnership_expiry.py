 """
 Daily expiry monitoring for partnerships.
 
 Usage (Windows PowerShell):
   cd backend
   python manage.py check_partnership_expiry
 
 Schedule via Windows Task Scheduler or cron (Linux) to run daily.
 """
 from django.core.management.base import BaseCommand
 from django.utils import timezone
 from django.core.mail import send_mail
 from django.conf import settings
 from partnerships.models import Partnership
 
 class Command(BaseCommand):
   help = "Marks partnerships as expired if end_date < today and sends notifications"
 
   def handle(self, *args, **options):
     today = timezone.localdate()
     qs = Partnership.objects.all()
     total = qs.count()
     expired_count = 0
     notified = 0
 
    for p in qs:
       try:
        if p.end_date and p.end_date < today:
          if p.status in {"approved", "active"} and p.status != "expired":
             p.status = "expired"
             p.save(update_fields=["status"])
             expired_count += 1
             try:
               subject = f"Partnership {p.id} expired"
               message = f"Your partnership between {p.main_contractor.name} and {p.partner_company.name} has expired on {p.end_date}."
               recipients = []
               # Best-effort recipient collection
               if getattr(p.owner, "email", None):
                 recipients.append(p.owner.email)
               if getattr(p.main_contractor, "owner", None) and getattr(p.main_contractor.owner, "email", None):
                 recipients.append(p.main_contractor.owner.email)
               if getattr(p.partner_company, "owner", None) and getattr(p.partner_company.owner, "email", None):
                 recipients.append(p.partner_company.owner.email)
               recipients = [r for r in recipients if r]
               if recipients:
                 send_mail(
                   subject,
                   message,
                   getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
                   recipients,
                   fail_silently=True,
                 )
                 notified += 1
               # SMS stub
               self.stdout.write(self.style.WARNING(f"[SMS] Partnership {p.id} expired ({p.end_date})"))
             except Exception:
               pass
       except Exception:
         continue
 
     self.stdout.write(self.style.SUCCESS(f"Checked {total} partnerships — expired marked: {expired_count}, emailed: {notified}"))
