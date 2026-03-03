from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Q
import re
from datetime import date
from licenses.models import License

@require_GET
def verify_by_number(request):
    num = (request.GET.get('licenseNumber') or request.GET.get('license_number') or '').strip()
    if not num:
        return JsonResponse({"valid": False, "detail": "License number is required."}, status=400)
    s = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFE58\uFE63\uFF0D]", "-", num)
    lic = (
        License.objects.filter(Q(license_number__iexact=s)).first()
        or License.objects.filter(
            Q(data__licenseNumber__iexact=s)
            | Q(data__license_number__iexact=s)
            | Q(data__registrationNumber__iexact=s)
            | Q(data__registration_number__iexact=s)
        ).first()
    )
    if not lic:
        return JsonResponse({"valid": False, "detail": "The license number you entered was not found in the database."}, status=404)
    not_expired = True
    try:
        if lic.expiry_date:
            not_expired = lic.expiry_date >= date.today()
    except Exception:
        not_expired = True
    data = {
        "id": lic.id,
        "license_number": lic.license_number or s,
        "status": lic.status,
        "issued_date": getattr(lic, "issued_date", None),
        "expiry_date": getattr(lic, "expiry_date", None),
        "company_name": (isinstance(lic.data, dict) and (lic.data.get("company_name") or lic.data.get("companyName"))) or "",
        "valid": (str(lic.status or "").lower() in ("approved", "active")) and not_expired,
    }
    return JsonResponse(data, status=200)
