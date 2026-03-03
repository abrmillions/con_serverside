from rest_framework import viewsets, permissions
from .models import Payment
from .serializers import PaymentSerializer
from datetime import date


class IsPayerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.payer == request.user


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated, IsPayerOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Payment.objects.all()
        return Payment.objects.filter(payer=user)

    def perform_create(self, serializer):
        obj = serializer.save(payer=self.request.user)
        try:
            md = {}
            try:
                md = serializer.validated_data.get('metadata') or {}
            except Exception:
                md = {}
            app_id = md.get('application_id') or self.request.data.get('application_id')
            if app_id and obj.status == 'completed':
                try:
                    from applications.models import Application
                    from systemsettings.models import SystemSettings
                    from licenses.models import License
                    from applications.models import ApplicationLog
                    app = Application.objects.filter(id=app_id).first()
                    if app:
                        data = app.data if isinstance(app.data, dict) else {}
                        data['paymentVerified'] = True
                        app.data = data
                        app.save(update_fields=['data'])
                        try:
                            settings = SystemSettings.get_solo()
                            if settings.auto_approval and app.is_renewal:
                                base_data = data if isinstance(data, dict) else {}
                                today = date.today()
                                base = getattr(app, 'previous_license', None)
                                base_date = getattr(base, 'expiry_date', None) or today
                                rp = base_data.get('renewalPeriod') or base_data.get('renewal_period')
                                years = 1
                                if isinstance(rp, (int, float)) and rp:
                                    years = int(rp)
                                elif isinstance(rp, str):
                                    import re
                                    m = re.search(r'(\d+)', rp)
                                    if m:
                                        years = int(m.group(1))
                                new_expiry = date(base_date.year + max(1, years), base_date.month, base_date.day)
                                issue_dt = base_date
                                # Update existing license in place to satisfy unique owner+license_type constraint
                                lic = getattr(app, "previous_license", None)
                                if lic:
                                    merged_data = {
                                        **(lic.data if isinstance(lic.data, dict) else {}),
                                        **base_data,
                                        "issueDate": issue_dt.isoformat(),
                                        "expiryDate": new_expiry.isoformat(),
                                        "application_id": app.id,
                                        "subtype": app.subtype,
                                        "licenseNumber": lic.license_number,
                                    }
                                    lic.issued_by = self.request.user
                                    lic.issued_date = issue_dt
                                    lic.expiry_date = new_expiry
                                    lic.data = merged_data
                                    lic.status = "active"
                                    lic.save()
                                app.approve()
                                try:
                                    ApplicationLog.objects.create(
                                        application=app,
                                        actor=self.request.user,
                                        action="approved",
                                        details="Auto-approved after payment"
                                    )
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

    def perform_update(self, serializer):
        prev = serializer.instance
        obj = serializer.save()
        try:
            if obj.status == 'completed':
                md = getattr(obj, 'metadata', None) or {}
                app_id = None
                try:
                    app_id = md.get('application_id')
                except Exception:
                    app_id = None
                if not app_id:
                    app_id = self.request.data.get('application_id')
                if app_id:
                    try:
                        from applications.models import Application
                        from systemsettings.models import SystemSettings
                        from licenses.models import License
                        from applications.models import ApplicationLog
                        app = Application.objects.filter(id=app_id).first()
                        if app:
                            data = app.data if isinstance(app.data, dict) else {}
                            data['paymentVerified'] = True
                            app.data = data
                            app.save(update_fields=['data'])
                            try:
                                settings = SystemSettings.get_solo()
                                if settings.auto_approval and app.is_renewal:
                                    base_data = data if isinstance(data, dict) else {}
                                    today = date.today()
                                    base = getattr(app, 'previous_license', None)
                                    base_date = getattr(base, 'expiry_date', None) or today
                                    rp = base_data.get('renewalPeriod') or base_data.get('renewal_period')
                                    years = 1
                                    if isinstance(rp, (int, float)) and rp:
                                        years = int(rp)
                                    elif isinstance(rp, str):
                                        import re
                                        m = re.search(r'(\d+)', rp)
                                        if m:
                                            years = int(m.group(1))
                                    new_expiry = date(base_date.year + max(1, years), base_date.month, base_date.day)
                                    issue_dt = base_date
                                    # Update existing license in place to satisfy unique owner+license_type constraint
                                    lic = getattr(app, "previous_license", None)
                                    if lic:
                                        merged_data = {
                                            **(lic.data if isinstance(lic.data, dict) else {}),
                                            **base_data,
                                            "issueDate": issue_dt.isoformat(),
                                            "expiryDate": new_expiry.isoformat(),
                                            "application_id": app.id,
                                            "subtype": app.subtype,
                                            "licenseNumber": lic.license_number,
                                        }
                                        lic.issued_by = self.request.user
                                        lic.issued_date = issue_dt
                                        lic.expiry_date = new_expiry
                                        lic.data = merged_data
                                        lic.status = "active"
                                        lic.save()
                                    app.approve()
                                    try:
                                        ApplicationLog.objects.create(
                                            application=app,
                                            actor=self.request.user,
                                            action="approved",
                                            details="Auto-approved after payment"
                                        )
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                    except Exception:
                        pass
        except Exception:
            pass
