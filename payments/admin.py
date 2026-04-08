from django.contrib import admin
from django.contrib.admin.sites import AlreadyRegistered
from django.contrib import messages
from django.db import transaction
from .models import Payment
from datetime import date
from django.urls import path, reverse
from django.shortcuts import redirect

class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id", "payer", "amount", "currency", "status",
        "meta_purpose", "meta_license_id", "meta_license_number",
        "meta_payment_method", "meta_business_name", "meta_payment_phone", "meta_account_number",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("payer__email", "payer__username")
    readonly_fields = (
        "payer", "amount", "currency", "status", "created_at", "tx_ref", "chapa_tx_id",
        "meta_purpose", "meta_license_id", "meta_license_number",
        "meta_license_section", "meta_license_category",
        "meta_payment_method", "meta_business_name", "meta_contact_person",
        "meta_email", "meta_business_phone", "meta_payment_phone",
        "meta_country_code", "meta_local_number", "meta_total_digits",
        "meta_account_number",
        "metadata",
    )

    fieldsets = (
        ("Payment", {
            "fields": ("payer", "amount", "currency", "status", "created_at", "tx_ref", "chapa_tx_id"),
        }),
        ("Certificate & Business Details", {
            "fields": (
                "meta_purpose", "meta_license_id", "meta_license_number",
                "meta_license_section", "meta_license_category",
                "meta_business_name", "meta_contact_person", "meta_email", "meta_business_phone",
            ),
        }),
        ("Method Details", {
            "fields": (
                "meta_payment_method", "meta_payment_phone", "meta_country_code", "meta_local_number", "meta_total_digits",
                "meta_account_number",
            ),
        }),
        ("Raw Metadata", {
            "classes": ("collapse",),
            "fields": ("metadata",),
        }),
    )
    change_form_template = "payments/change_form.html"

    def _md(self, obj):
        try:
            return getattr(obj, "metadata", None) or {}
        except Exception:
            return {}

    def meta_purpose(self, obj):
        return self._md(obj).get("purpose") or ""
    meta_purpose.short_description = "Purpose"

    def meta_license_id(self, obj):
        return self._md(obj).get("license_id") or ""
    meta_license_id.short_description = "License ID"

    def meta_license_number(self, obj):
        return self._md(obj).get("license_number") or ""
    meta_license_number.short_description = "License Number"

    def meta_license_section(self, obj):
        return self._md(obj).get("license_section") or ""
    meta_license_section.short_description = "Section"

    def meta_license_category(self, obj):
        return self._md(obj).get("license_category") or ""
    meta_license_category.short_description = "Category"

    def meta_payment_method(self, obj):
        return self._md(obj).get("payment_method") or ""
    meta_payment_method.short_description = "Method"

    def meta_business_name(self, obj):
        return self._md(obj).get("business_name") or ""
    meta_business_name.short_description = "Business"

    def meta_contact_person(self, obj):
        return self._md(obj).get("contact_person") or ""
    meta_contact_person.short_description = "Contact"

    def meta_email(self, obj):
        return self._md(obj).get("email") or ""
    meta_email.short_description = "Email"

    def meta_business_phone(self, obj):
        return self._md(obj).get("business_phone") or ""
    meta_business_phone.short_description = "Business Phone"

    def meta_payment_phone(self, obj):
        return self._md(obj).get("payment_phone") or ""
    meta_payment_phone.short_description = "Payment Phone"

    def meta_country_code(self, obj):
        return self._md(obj).get("country_code") or ""
    meta_country_code.short_description = "Country Code"

    def meta_local_number(self, obj):
        return self._md(obj).get("local_number") or ""
    meta_local_number.short_description = "Local Number"

    def meta_total_digits(self, obj):
        return self._md(obj).get("total_digits") or ""
    meta_total_digits.short_description = "Total Digits"

    def meta_account_number(self, obj):
        return self._md(obj).get("account_number") or ""
    meta_account_number.short_description = "Account Number"

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
                if pay.status not in ("success", "active"):
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

    actions = ("mark_success", "mark_failed", "mark_pending", "mark_active")

    def _run_post_complete(self, request, payment_ids):
        actor_id = getattr(request.user, "id", None)
        def _after_commit():
            for pid in payment_ids:
                try:
                    from applications.models import Application, ApplicationLog
                    from licenses.models import License
                    pay = Payment.objects.filter(id=pid).first()
                    if not pay:
                        continue
                    md = getattr(pay, "metadata", None) or {}
                    app_id = md.get("application_id")
                    if not app_id:
                        continue
                    if pay.status not in ("success", "active"):
                        continue
                    with transaction.atomic():
                        app = Application.objects.select_for_update().filter(id=app_id).first()
                        if not app:
                            continue
                        dd = app.data if isinstance(app.data, dict) else {}
                        dd["paymentVerified"] = True
                        app.data = dd
                        app.save(update_fields=["data"])
                        if app.status == "approved":
                            continue
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
                    pass
        try:
            transaction.on_commit(_after_commit)
        except Exception:
            pass

    def mark_success(self, request, queryset):
        ids = []
        for p in queryset:
            try:
                p.status = "success"
                p.save(update_fields=["status"])
                ids.append(p.id)
            except Exception:
                pass
        if ids:
            self._run_post_complete(request, ids)
        messages.success(request, f"Marked {len(ids)} payments as success")
    mark_success.short_description = "Mark selected payments as success"

    def mark_active(self, request, queryset):
        ids = []
        for p in queryset:
            try:
                p.status = "active"
                p.save(update_fields=["status"])
                ids.append(p.id)
            except Exception:
                pass
        if ids:
            self._run_post_complete(request, ids)
        messages.success(request, f"Marked {len(ids)} payments as active")
    mark_active.short_description = "Mark selected payments as active"

    def mark_failed(self, request, queryset):
        count = 0
        for p in queryset:
            try:
                p.status = "failed"
                p.save(update_fields=["status"])
                count += 1
            except Exception:
                pass
        messages.success(request, f"Marked {count} payments as failed")
    mark_failed.short_description = "Mark selected payments as failed"

    def mark_pending(self, request, queryset):
        count = 0
        for p in queryset:
            try:
                p.status = "pending"
                p.save(update_fields=["status"])
                count += 1
            except Exception:
                pass
        messages.success(request, f"Marked {count} payments as pending")
    mark_pending.short_description = "Mark selected payments as pending"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("<int:payment_id>/mark_success/", self.admin_site.admin_view(self.mark_success_view), name="payments_payment_mark_success"),
            path("<int:payment_id>/mark_active/", self.admin_site.admin_view(self.mark_active_view), name="payments_payment_mark_active"),
            path("<int:payment_id>/mark_failed/", self.admin_site.admin_view(self.mark_failed_view), name="payments_payment_mark_failed"),
            path("<int:payment_id>/mark_pending/", self.admin_site.admin_view(self.mark_pending_view), name="payments_payment_mark_pending"),
        ]
        return custom + urls

    def _redirect_change(self, payment_id):
        url = reverse("admin:payments_payment_change", args=[payment_id])
        return redirect(url)

    def mark_success_view(self, request, payment_id):
        p = Payment.objects.filter(id=payment_id).first()
        if p:
            p.status = "success"
            p.save(update_fields=["status"])
            self._run_post_complete(request, [payment_id])
            messages.success(request, "Payment marked as success")
        return self._redirect_change(payment_id)

    def mark_active_view(self, request, payment_id):
        p = Payment.objects.filter(id=payment_id).first()
        if p:
            p.status = "active"
            p.save(update_fields=["status"])
            self._run_post_complete(request, [payment_id])
            messages.success(request, "Payment marked as active")
        return self._redirect_change(payment_id)

    def mark_failed_view(self, request, payment_id):
        p = Payment.objects.filter(id=payment_id).first()
        if p:
            p.status = "failed"
            p.save(update_fields=["status"])
            messages.success(request, "Payment marked as failed")
        return self._redirect_change(payment_id)

    def mark_pending_view(self, request, payment_id):
        p = Payment.objects.filter(id=payment_id).first()
        if p:
            p.status = "pending"
            p.save(update_fields=["status"])
            messages.success(request, "Payment marked as pending")
        return self._redirect_change(payment_id)

try:
    admin.site.unregister(Payment)
except Exception:
    pass

try:
    admin.site.register(Payment, PaymentAdmin)
except AlreadyRegistered:
    pass
