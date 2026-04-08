from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from django.db import models
from django.db.models import Count, Sum, Value
from django.db.models.functions import TruncMonth
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
from django.utils import timezone

from licenses.models import License
from applications.models import Application
from partnerships.models import Partnership
from vehicles.models import Vehicle
# from payments.models import Payment # Assuming payment model exists, if not we will mock or skip

User = get_user_model()

@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_analytics_view(request):
    # Time range handling: default to 180 days (6 months)
    range_param = request.query_params.get('range', 'month')
    
    if range_param == 'week':
        days_ago = 7
    elif range_param == 'month':
        days_ago = 30
    elif range_param == 'quarter':
        days_ago = 90
    elif range_param == 'year':
        days_ago = 365
    else:
        days_ago = 30 # Default to month if range is unknown
        
    start_date = timezone.now() - timedelta(days=days_ago)
    
    # 1. Total Applications & Trends
    # Group by appropriate time period based on range
    if days_ago <= 30:
        # Use day grouping for shorter ranges
        from django.db.models.functions import TruncDay
        trunc_func = TruncDay
        date_format = '%d %b'
    else:
        # Use month grouping for longer ranges
        from django.db.models.functions import TruncMonth
        trunc_func = TruncMonth
        date_format = '%b'
    
    # We'll aggregate counts from all application-like models
    # Applications (Standard licenses)
    app_stats = Application.objects.filter(created_at__gte=start_date)\
        .annotate(period=trunc_func('created_at'))\
        .values('period')\
        .annotate(
            applications=Count('id'),
            approved=Count('id', filter=models.Q(status='approved')),
            rejected=Count('id', filter=models.Q(status='rejected')),
            pending=Count('id', filter=models.Q(status='pending')),
            active=Value(0, output_field=models.IntegerField())
        )
        
    # Partnerships
    partnership_stats = Partnership.objects.filter(created_at__gte=start_date)\
        .annotate(period=trunc_func('created_at'))\
        .values('period')\
        .annotate(
            applications=Count('id'),
            approved=Count('id', filter=models.Q(status='approved')),
            rejected=Count('id', filter=models.Q(status='rejected')),
            pending=Count('id', filter=models.Q(status__icontains='pending') | models.Q(status__icontains='awaiting')),
            active=Count('id', filter=models.Q(status='active'))
        )
        
    # Vehicles
    vehicle_stats = Vehicle.objects.filter(registered_at__gte=start_date)\
        .annotate(period=trunc_func('registered_at'))\
        .values('period')\
        .annotate(
            applications=Count('id'),
            approved=Count('id', filter=models.Q(status='approved')),
            rejected=Count('id', filter=models.Q(status='rejected')),
            pending=Count('id', filter=models.Q(status='pending')),
            active=Count('id', filter=models.Q(status='active'))
        )
        
    # Combine results into a timeline
    trends_map = {}
    
    def add_to_trends(queryset_results):
        for entry in queryset_results:
            if not entry.get('period'):
                continue
            m_key = entry['period'].strftime(date_format)
            if m_key not in trends_map:
                trends_map[m_key] = {"month": m_key, "applications": 0, "approved": 0, "rejected": 0, "pending": 0, "active": 0}
            
            trends_map[m_key]["applications"] += entry['applications']
            trends_map[m_key]["approved"] += entry['approved']
            trends_map[m_key]["rejected"] += entry['rejected']
            trends_map[m_key]["pending"] += entry['pending']
            trends_map[m_key]["active"] += entry.get('active', 0)
            
    add_to_trends(app_stats)
    add_to_trends(partnership_stats)
    add_to_trends(vehicle_stats)
    
    # Sort application trends chronologically if needed (optional but good)
    # Since we use period names as keys, we should ideally sort by date
    # Convert map to list and return as is for now as Recharts handles it well
    application_trends = list(trends_map.values())
    
    # Ensure trends are sorted by date
    # Re-fetch trends in sorted order for better visualization
    all_periods = sorted(trends_map.keys(), key=lambda x: datetime.strptime(x, date_format))
    application_trends = [trends_map[p] for p in all_periods]


    # 2. License Distribution
    # Define all types we want to track in the chart
    types_to_track = [
        ("Contractor License", "Contractor License"),
        ("Professional License", "Professional License"),
        ("Import/Export License", "Import/Export License"),
        ("Partnership Registration", "Partnership Registration"),
        ("Vehicle Registration", "Vehicle Registration"),
    ]
    
    license_types = []
    colors = ["#3B82F6", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899", "#06B6D4", "#F43F5E"]
    
    for i, (internal_name, display_name) in enumerate(types_to_track):
        count = 0
        if internal_name == "Partnership Registration":
            count = Partnership.objects.count()
        elif internal_name == "Vehicle Registration":
            count = Vehicle.objects.count()
        else:
            # For standard licenses, count applications instead of issued licenses
            # to reflect all registrations (consistent with Partnerships/Vehicles)
            count = Application.objects.filter(
                models.Q(license_type__iexact=internal_name) | 
                models.Q(license_type__icontains="Import")
            ).count() if "Import" in internal_name else Application.objects.filter(license_type=internal_name).count()
            
        license_types.append({
            "name": display_name,
            "value": count,
            "color": colors[i % len(colors)]
        })

    # 3. Revenue (Real counting from Payment model)
    try:
        from payments.models import Payment
        # Consider both 'success' and 'active' (if active means paid/confirmed in this context, 
        # but usually 'success' is the standard for completed payments)
        paid_payments = Payment.objects.filter(status__in=['success', 'active'])
        
        # Calculate total revenue across all currencies (assuming ETB is the main one)
        # If there are multiple currencies, we would need conversion, but for now we sum ETB
        total_revenue = paid_payments.filter(currency='ETB').aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Monthly revenue trends for the selected range
        monthly_revenue = paid_payments.filter(created_at__gte=start_date, currency='ETB')\
            .annotate(period=trunc_func('created_at'))\
            .values('period')\
            .annotate(revenue=Sum('amount'))\
            .order_by('period')
            
        revenue_data = []
        # Ensure all periods in the range are represented even if 0
        revenue_map = {entry['period'].strftime(date_format): float(entry['revenue']) for entry in monthly_revenue if entry.get('period')}
        
        # Use the same sorted periods as application trends for consistency
        for p in all_periods:
            revenue_data.append({
                "month": p,
                "revenue": revenue_map.get(p, 0.0)
            })
        
    except (ImportError, Exception) as e:
        print(f"Error calculating revenue: {e}")
        total_revenue = 0
        revenue_data = []

    # 4. Active Users
    active_users = User.objects.filter(is_active=True).count()

    # 5. Key Metrics
    # Include all registration types in global metrics
    total_apps_count = Application.objects.count() + Partnership.objects.count() + Vehicle.objects.count()
    
    apps_approved = Application.objects.filter(status='approved').count()
    partnerships_approved = Partnership.objects.filter(status='approved').count()
    vehicles_approved = Vehicle.objects.filter(status='approved').count()
    
    approved_apps_count = apps_approved + partnerships_approved + vehicles_approved
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
            { "type": "Partnership", "avgDays": 12.5 },
            { "type": "Vehicle", "avgDays": 4.2 },
        ]
    }

    return Response(data)


@api_view(["GET"])
@permission_classes([AllowAny])
def stats_view(request):
    total = License.objects.count()
    approved = License.objects.filter(status__in=["approved", "active"]).count()
    
    # Combined metrics for all registration types
    total_apps_count = Application.objects.count() + Partnership.objects.count() + Vehicle.objects.count()
    
    # Use Count with filter to avoid multiple queries and potential errors
    apps_approved = Application.objects.filter(status='approved').count()
    partnerships_approved = Partnership.objects.filter(status='approved').count()
    vehicles_approved = Vehicle.objects.filter(status='approved').count()
    
    approved_apps_count = apps_approved + partnerships_approved + vehicles_approved
    approval_rate = (approved_apps_count / total_apps_count * 100) if total_apps_count > 0 else 0
    active_users = User.objects.filter(is_active=True).count()

    licensed_contractors = Application.objects.filter(license_type="Contractor License", status__in=["approved", "active"]).count()
    professionals = Application.objects.filter(license_type="Professional License", status__in=["approved", "active"]).count()
    import_export_licensed = Application.objects.filter(license_type="Import/Export License", status__in=["approved", "active"]).count()

    contractor_applications = Application.objects.filter(license_type="Contractor License").count()
    professional_applications = Application.objects.filter(license_type="Professional License").count()
    import_export_applications = Application.objects.filter(license_type="Import/Export License").count()
    partnership_applications = Partnership.objects.count()
    vehicle_applications = Vehicle.objects.count()
    
    professional_pending = Application.objects.filter(license_type="Professional License", status="pending").count()
    professional_approved = Application.objects.filter(license_type="Professional License", status__in=["approved"]).count()

    # Licenses by type breakdown (using Application model to reflect all submissions)
    def license_counts_for(lic_type: str):
        qs = Application.objects.filter(license_type=lic_type)
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
            "partnership": partnership_applications,
            "vehicle": vehicle_applications,
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
            "partnership": {"total": partnership_applications},
            "vehicle": {"total": vehicle_applications},
        },
    }

    return Response(data)
