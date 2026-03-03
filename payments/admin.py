from django.contrib import admin
from django.contrib.admin.sites import AlreadyRegistered
from django.db import transaction
from .models import Payment
from datetime import date

class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "payer", "amount", "currency", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("payer__email", "payer__username")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        def _after_commit(payment_id: int, actor_id: int):
            try:
                from applications.models import Application, ApplicationLog
                from licenses.models import License
                pay = Payment.objects.filter(id=payment_id).first()
                if not pay:
                    return
                md = getattr(pay, "metadata", None) or {}
                app_id = md.get("application_id")
                if not app_id:
                    return
                if pay.status not in ("completed", "active"):
                    return
                with transaction.atomic():
                    app = Application.objects.select_for_update().filter(id=app_id).first()
                    if not app:
                        return
                    dd = app.data if isinstance(app.data, dict) else {}
                    dd["paymentVerified"] = True
                    app.data = dd
                    app.save(update_fields=["data"])
                    if app.status == "approved":
                        return
                    today = date.today()
                    base = getattr(app, "previous_license", None)
                    base_date = getattr(base, "expiry_date", None) or today
                    rp = dd.get("renewalPeriod") or dd.get("renewal_period")
                    years = 1
                    try:
                        if isinstance(rp, (int, float)) and rp:
                            years = int(rp)
                        elif isinstance(rp, str):
                            import re
                            m = re.search(r"(\d+)", rp)
                            if m:
                                years = int(m.group(1))
                    except Exception:
                        years = 1
                    new_expiry = date(base_date.year + max(1, years), base_date.month, base_date.day)
                    # Update existing license in place to satisfy unique owner+license_type constraint
                    lic = getattr(app, "previous_license", None)
                    if lic:
                        merged_data = {
                            **(lic.data if isinstance(lic.data, dict) else {}),
                            **dd,
                            "subtype": app.subtype,
                            "licenseNumber": lic.license_number,
                            "issueDate": base_date.isoformat(),
                            "expiryDate": new_expiry.isoformat(),
                            "application_id": app.id,
                        }
                        lic.issued_by_id = actor_id
                        lic.issued_date = base_date
                        lic.expiry_date = new_expiry
                        lic.data = merged_data
                        lic.status = "active"
                        lic.save()
                    app.approve()
                    try:
                        ApplicationLog.objects.create(
                            application=app,
                            actor_id=actor_id,
                            action="approved",
                            details="Approved via Payment status"
                        )
                    except Exception:
                        pass
            except Exception:
                # Swallow to avoid breaking post-commit handler
                pass
        try:
            transaction.on_commit(lambda: _after_commit(obj.id, getattr(request.user, "id", None)))
        except Exception:
            # If on_commit unavailable, do nothing to avoid atomic breakage
            pass

try:
    admin.site.unregister(Payment)
except Exception:
    pass

try:
    admin.site.register(Payment, PaymentAdmin)
except AlreadyRegistered:
    pass
