from rest_framework import serializers
from .models import License
from datetime import date


class LicenseSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source="owner.username")
    can_download = serializers.SerializerMethodField()
    license_photo_url = serializers.SerializerMethodField()
    license_photo_base64 = serializers.SerializerMethodField()
    application_status = serializers.SerializerMethodField()
    holder_full_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    grade = serializers.SerializerMethodField()

    class Meta:
        model = License
        # expose system-generated license_number and key dates for frontend
        fields = (
            "id",
            "owner",
            "holder_full_name",
            "company_name",
            "license_type",
            "license_number",
            "issued_date",
            "expiry_date",
            "qr_code_data",
            "data",
            "license_photo_url",
            "license_photo_base64",
            "application_status",
            "status",
            "created_at",
            "can_download",
            "grade",
        )
        read_only_fields = ("id", "owner", "created_at", "license_number", "issued_date", "expiry_date", "qr_code_data", "can_download")

    def get_can_download(self, obj):
        """Return whether the current request user may download this license.

        Rules: only owner or staff may download, and license must be approved/active
        and not expired.
        """
        request = self.context.get('request') if isinstance(self.context, dict) else None
        user = getattr(request, 'user', None)
        # Only owner or staff can download
        if not user:
            return False
        if not (user == obj.owner or getattr(user, 'is_staff', False)):
            return False

        # Status must be approved or active
        if obj.status not in ('approved', 'active'):
            return False

        # Must not be expired
        if getattr(obj, 'expiry_date', None) and obj.expiry_date < date.today():
            return False

        return True

    def get_license_photo_url(self, obj):
        request = self.context.get('request') if isinstance(self.context, dict) else None
        photo = getattr(obj, 'license_photo', None)
        if photo:
            try:
                url = photo.url
                if request:
                    return request.build_absolute_uri(url)
                return url
            except Exception:
                pass
        # Fallback to linked application photo if available
        try:
            app_id = None
            if isinstance(obj.data, dict):
                app_id = obj.data.get('application_id')
            app = None
            if app_id:
                from applications.models import Application
                app = Application.objects.filter(id=app_id).first()
            # Fallback: locate latest application by owner+license_type
            if not app:
                try:
                    from applications.models import Application
                    app = Application.objects.filter(applicant=obj.owner, license_type=obj.license_type).order_by('-created_at').first()
                except Exception:
                    app = None
            if app:
                preferred = ('profile_photo', 'professional_photo', 'company_representative_photo')
                try:
                    lt = getattr(app, 'license_type', None) or getattr(obj, 'license_type', None)
                    if lt == "Contractor License":
                        preferred = ('profile_photo', 'professional_photo', 'company_representative_photo')
                    elif lt == "Professional License":
                        preferred = ('professional_photo', 'profile_photo', 'company_representative_photo')
                    elif lt == "Import/Export License":
                        preferred = ('company_representative_photo', 'profile_photo', 'professional_photo')
                except Exception:
                    preferred = ('profile_photo', 'professional_photo', 'company_representative_photo')
                for fld in preferred:
                    af = getattr(app, fld, None)
                    if af:
                        try:
                            url = af.url
                            if request:
                                return request.build_absolute_uri(url)
                            return url
                        except Exception:
                            continue
                # Fallback: try linked Document images
                try:
                    docs = getattr(app, 'documents', None)
                    if docs:
                        # Prefer 'companyPhoto' document for Import/Export when available
                        try:
                            lt = getattr(app, 'license_type', None) or getattr(obj, 'license_type', None)
                        except Exception:
                            lt = None
                        if lt == "Import/Export License":
                            for doc in docs.all():
                                try:
                                    nm = str(getattr(doc, 'name', '') or '').strip().lower()
                                    f = getattr(doc, 'file', None)
                                    fn = str(getattr(f, 'name', '') or '')
                                    base = fn.split('/')[-1].lower() if fn else ''
                                    if ('representative' in nm) or ('representative' in base):
                                        url = f.url
                                        if request:
                                            return request.build_absolute_uri(url)
                                        return url
                                except Exception:
                                    continue
                        # Otherwise pick first image document
                        for doc in docs.all():
                            try:
                                f = getattr(doc, 'file', None)
                                name = getattr(f, 'name', '')
                                if isinstance(name, str) and name.lower().split('.')[-1] in ('jpg','jpeg','png','gif','webp'):
                                    url = f.url
                                    if request:
                                        return request.build_absolute_uri(url)
                                    return url
                            except Exception:
                                continue
                except Exception:
                    pass
        except Exception:
            pass
        # Fallback to owner's profile photo
        try:
            owner = getattr(obj, 'owner', None)
            if owner:
                pf = getattr(owner, 'profile_photo', None)
                if pf:
                    try:
                        url = pf.url
                        if request:
                            return request.build_absolute_uri(url)
                        return url
                    except Exception:
                        pass
        except Exception:
            pass
        return None
    
    def get_license_photo_base64(self, obj):
        try:
            def to_b64(p):
                import base64
                import mimetypes
                if not p or not hasattr(p, 'open'):
                    return None
                p.open('rb')
                try:
                    content = p.read()
                    b64 = base64.b64encode(content).decode('ascii')
                    mime = None
                    try:
                        mime = mimetypes.guess_type(getattr(p, 'name', ''), strict=False)[0]
                    except Exception:
                        mime = None
                    if not mime:
                        mime = 'image/jpeg'
                    return f"data:{mime};base64,{b64}"
                finally:
                    try:
                        p.close()
                    except Exception:
                        pass

            photo = getattr(obj, 'license_photo', None)
            data_url = to_b64(photo)
            if data_url:
                return data_url

            # Fallback to application photo
            try:
                app_id = None
                if isinstance(obj.data, dict):
                    app_id = obj.data.get('application_id')
                app = None
                if app_id:
                    from applications.models import Application
                    app = Application.objects.filter(id=app_id).first()
                if not app:
                    try:
                        from applications.models import Application
                        app = Application.objects.filter(applicant=obj.owner, license_type=obj.license_type).order_by('-created_at').first()
                    except Exception:
                        app = None
                if app:
                    preferred = ('profile_photo', 'professional_photo', 'company_representative_photo')
                    try:
                        lt = getattr(app, 'license_type', None) or getattr(obj, 'license_type', None)
                        if lt == "Contractor License":
                            preferred = ('profile_photo', 'professional_photo', 'company_representative_photo')
                        elif lt == "Professional License":
                            preferred = ('professional_photo', 'profile_photo', 'company_representative_photo')
                        elif lt == "Import/Export License":
                            preferred = ('company_representative_photo', 'profile_photo', 'professional_photo')
                    except Exception:
                        preferred = ('profile_photo', 'professional_photo', 'company_representative_photo')
                    for fld in preferred:
                        af = getattr(app, fld, None)
                        data_url = to_b64(af)
                        if data_url:
                            return data_url
                    # Fallback: try linked Document images
                    try:
                        docs = getattr(app, 'documents', None)
                        if docs:
                            # Prefer 'companyPhoto' for Import/Export license
                            try:
                                lt = getattr(app, 'license_type', None) or getattr(obj, 'license_type', None)
                            except Exception:
                                lt = None
                            if lt == "Import/Export License":
                                for doc in docs.all():
                                    try:
                                        nm = str(getattr(doc, 'name', '') or '').strip().lower()
                                        f = getattr(doc, 'file', None)
                                        name = str(getattr(f, 'name', '') or '')
                                        base = name.split('/')[-1].lower() if name else ''
                                        if ('representative' in nm) or ('representative' in base):
                                            fh = None
                                            try:
                                                storage = f.storage
                                                fh = storage.open(f.name, 'rb')
                                                content = fh.read()
                                            finally:
                                                try:
                                                    if fh: fh.close()
                                                except Exception:
                                                    pass
                                            import base64, mimetypes
                                            b64 = base64.b64encode(content).decode('ascii')
                                            mime = mimetypes.guess_type(name, strict=False)[0] or 'image/jpeg'
                                            return f"data:{mime};base64,{b64}"
                                    except Exception:
                                        continue
                            # Otherwise pick first image document
                            for doc in docs.all():
                                try:
                                    f = getattr(doc, 'file', None)
                                    name = getattr(f, 'name', '')
                                    if isinstance(name, str) and name.lower().split('.')[-1] in ('jpg','jpeg','png','gif','webp'):
                                        fh = None
                                        try:
                                            storage = f.storage
                                            fh = storage.open(f.name, 'rb')
                                            content = fh.read()
                                        finally:
                                            try:
                                                if fh: fh.close()
                                            except Exception:
                                                pass
                                        import base64, mimetypes
                                        b64 = base64.b64encode(content).decode('ascii')
                                        mime = mimetypes.guess_type(name, strict=False)[0] or 'image/jpeg'
                                        return f"data:{mime};base64,{b64}"
                                except Exception:
                                    continue
                    except Exception:
                        pass
            except Exception:
                pass
            # Fallback to owner's profile photo
            try:
                owner = getattr(obj, 'owner', None)
                if owner:
                    pf = getattr(owner, 'profile_photo', None)
                    data_url = to_b64(pf)
                    if data_url:
                        return data_url
            except Exception:
                pass
        except Exception:
            pass
        return None

    def get_application_status(self, obj):
        # Try to find linked application id in license data and return its status
        try:
            app_id = None
            if isinstance(obj.data, dict):
                app_id = obj.data.get('application_id')
            if app_id:
                from applications.models import Application
                app = Application.objects.filter(id=app_id).first()
                if app:
                    return app.status
        except Exception:
            pass
        return None

    def get_holder_full_name(self, obj):
        try:
            owner = getattr(obj, 'owner', None)
            if owner:
                fn = getattr(owner, 'get_full_name', None)
                if callable(fn):
                    name = fn()
                    if name and str(name).strip():
                        return str(name).strip()
                return getattr(owner, 'email', getattr(owner, 'username', None))
        except Exception:
            return None

    def get_company_name(self, obj):
        try:
            # Prefer explicit company_name/companyName in license data
            if isinstance(obj.data, dict):
                val = obj.data.get('company_name') or obj.data.get('companyName')
                if val and str(val).strip():
                    return str(val).strip()
                # Fallback: pull from linked application, if present
                app_id = obj.data.get('application_id')
                if app_id:
                    from applications.models import Application
                    app = Application.objects.filter(id=app_id).first()
                    if app and isinstance(app.data, dict):
                        val2 = app.data.get('company_name') or app.data.get('companyName')
                        if val2 and str(val2).strip():
                            return str(val2).strip()
            return None
        except Exception:
            return None

    def get_grade(self, obj):
        try:
            lt = getattr(obj, 'license_type', '') or ''
            if 'contractor' not in str(lt).lower():
                return None
            d = obj.data if isinstance(obj.data, dict) else {}
            raw = d.get('grade') or d.get('licenseType') or d.get('category')
            if not raw:
                return None
            s = str(raw).strip().lower()
            if 'grade-a' in s or s == 'a' or 'grade a' in s:
                return 'Grade A'
            if 'grade-b' in s or s == 'b' or 'grade b' in s:
                return 'Grade B'
            if 'grade-c' in s or s == 'c' or 'grade c' in s:
                return 'Grade C'
            if 'specialized' in s:
                return 'Specialized Contractor'
            return str(raw)
        except Exception:
            return None
