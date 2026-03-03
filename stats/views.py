from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from django.db import models
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
from django.utils import timezone

from licenses.models import License
from applications.models import Application
# from payments.models import Payment # Assuming payment model exists, if not we will mock or skip

User = get_user_model()

@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_analytics_view(request):
    # Time range handling could be added here (e.g. ?range=month)
    
    # 1. Total Applications & Trends
    # Group by month for the last 6 months
    six_months_ago = timezone.now() - timedelta(days=180)
    
    monthly_stats = Application.objects.filter(created_at__gte=six_months_ago)\
        .annotate(month=TruncMonth('created_at'))\
        .values('month')\
        .annotate(
            applications=Count('id'),
            approved=Count('id', filter=models.Q(status='approved')),
            rejected=Count('id', filter=models.Q(status='rejected')),
            pending=Count('id', filter=models.Q(status='pending'))
        ).order_by('month')
        
    application_trends = []
    for entry in monthly_stats:
        application_trends.append({
            "month": entry['month'].strftime('%b'),
            "applications": entry['applications'],
            "approved": entry['approved'],
            "rejected": entry['rejected'],
            "pending": entry['pending']
        })

    # 2. License Distribution
    license_counts = License.objects.values('license_type').annotate(count=Count('id'))
    license_types = []
    colors = ["#3B82F6", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899"]
    for i, item in enumerate(license_counts):
        license_types.append({
            "name": item['license_type'].replace('_', ' ').title(),
            "value": item['count'],
            "color": colors[i % len(colors)]
        })

    # 3. Revenue (Mocked for now if Payment model is not fully integrated or populated)
    # We can try to import Payment, if it fails use 0
    try:
        from payments.models import Payment
        total_revenue = Payment.objects.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Monthly revenue
        monthly_revenue = Payment.objects.filter(created_at__gte=six_months_ago, status='completed')\
            .annotate(month=TruncMonth('created_at'))\
            .values('month')\
            .annotate(revenue=Sum('amount'))\
            .order_by('month')
            
        revenue_data = [{
            "month": entry['month'].strftime('%b'),
            "revenue": float(entry['revenue'])
        } for entry in monthly_revenue]
        
    except ImportError:
        total_revenue = 0
        revenue_data = []

    # 4. Active Users
    active_users = User.objects.filter(is_active=True).count()

    # 5. Key Metrics
    total_apps_count = Application.objects.count()
    approved_apps_count = Application.objects.filter(status='approved').count()
    approval_rate = (approved_apps_count / total_apps_count * 100) if total_apps_count > 0 else 0

    data = {
        "applicationTrends": application_trends,
        "licenseTypes": license_types,
        "revenueData": revenue_data,
        "totalApplications": total_apps_count,
        "approvalRate": round(approval_rate, 1),
        "totalRevenue": float(total_revenue),
        "activeUsers": active_users,
        # Processing times would require complex log analysis, mocking for simplicity or implementing later
        "processingTimes": [
            { "type": "Contractor", "avgDays": 7.2 },
            { "type": "Professional", "avgDays": 5.8 },
            { "type": "Import/Export", "avgDays": 9.3 },
        ]
    }

    return Response(data)


@api_view(["GET"])
@permission_classes([AllowAny])
def stats_view(request):
    total = License.objects.count()
    approved = License.objects.filter(status__in=["approved", "active"]).count()
    total_apps_count = Application.objects.count()
    approved_apps_count = Application.objects.filter(status='approved').count()
    approval_rate = (approved_apps_count / total_apps_count * 100) if total_apps_count > 0 else 0
    active_users = User.objects.filter(is_active=True).count()

    licensed_contractors = License.objects.filter(license_type="Contractor License", status__in=["approved", "active"]).count()
    professionals = License.objects.filter(license_type="Professional License", status__in=["approved", "active"]).count()
    import_export_licensed = License.objects.filter(license_type="Import/Export License", status__in=["approved", "active"]).count()

    contractor_applications = Application.objects.filter(license_type="Contractor License").count()
    professional_applications = Application.objects.filter(license_type="Professional License").count()
    import_export_applications = Application.objects.filter(license_type="Import/Export License").count()
    professional_pending = Application.objects.filter(license_type="Professional License", status="pending").count()
    professional_approved = Application.objects.filter(license_type="Professional License", status__in=["approved"]).count()

    # Licenses by type breakdown
    def license_counts_for(lic_type: str):
        qs = License.objects.filter(license_type=lic_type)
        return {
            "total": qs.count(),
            "approved": qs.filter(status="approved").count(),
            "rejected": qs.filter(status="rejected").count(),
            "pending": qs.filter(status="pending").count(),
            "active": qs.filter(status="active").count(),
            "revoked": qs.filter(status="revoked").count(),
        }

    digital_approval_pct = int(round((approved / total) * 100)) if total else 0

    data = {
        "licensed_contractors": licensed_contractors,
        "professionals": professionals,
        "import_export_licensed": import_export_licensed,
        "approval_rate": round(approval_rate, 1),
        "active_users": active_users,
        "digital_approval_pct": digital_approval_pct,
        "online_access_24_7": True,
        "applications_by_type": {
            "contractor": contractor_applications,
            "professional": professional_applications,
            "import_export": import_export_applications,
        },
        "professional_metrics": {
            "applications": professional_applications,
            "active_licenses": professionals,
            "pending_applications": professional_pending,
            "approved_applications": professional_approved,
        },
        "licenses_by_type": {
            "contractor": license_counts_for("Contractor License"),
            "professional": license_counts_for("Professional License"),
            "import_export": license_counts_for("Import/Export License"),
        },
    }

    return Response(data)
