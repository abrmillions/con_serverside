from django.utils import timezone
from datetime import date

def activate_license(user):
    """
    Simplified license activation logic. 
    In your system, you might need more complex logic.
    """
    try:
        # Check for related license profile
        if hasattr(user, 'licenseprofile'):
            profile = user.licenseprofile
            profile.status = "active"
            profile.save()
        
        # Or look for actual licenses related to the user
        from licenses.models import License
        License.objects.filter(owner=user, status='pending').update(status='active')
    except Exception:
        pass

def process_successful_payment(payment):
    """
    Handles post-payment logic: 
    1. Updates application payment status
    2. Triggers auto-approval for renewals if enabled
    Returns: dict with 'auto_approved' boolean
    """
    result = {"auto_approved": False}
    try:
        metadata = payment.metadata or {}
        app_id = metadata.get('application_id')
        
        if not app_id:
            return result

        from applications.models import Application, ApplicationLog
        from systemsettings.models import SystemSettings
        from licenses.models import License
        
        app = Application.objects.filter(id=app_id).first()
        if not app:
            return result

        # Mark payment as verified in application data
        app_data = app.data if isinstance(app.data, dict) else {}
        app_data['paymentVerified'] = True
        app.data = app_data
        app.save(update_fields=['data'])

        # Check for Auto-Approval logic
        try:
            settings = SystemSettings.get_solo()
            if settings.auto_approval and app.is_renewal:
                today = date.today()
                # Get previous license to calculate new expiry
                prev_lic = getattr(app, 'previous_license', None)
                base_date = getattr(prev_lic, 'expiry_date', None) or today
                
                # Determine renewal period in years
                rp = app_data.get('renewalPeriod') or app_data.get('renewal_period') or metadata.get('renewal_period')
                years = 1
                if isinstance(rp, (int, float)) and rp:
                    years = int(rp)
                elif isinstance(rp, str):
                    import re
                    m = re.search(r'(\d+)', rp)
                    if m:
                        years = int(m.group(1))
                
                new_expiry = date(base_date.year + max(1, years), base_date.month, base_date.day)
                issue_dt = today # Activation happens today

                if prev_lic:
                    # Update existing license in place
                    lic_data = prev_lic.data if isinstance(prev_lic.data, dict) else {}
                    merged_data = {
                        **lic_data,
                        **app_data,
                        "issueDate": issue_dt.isoformat(),
                        "expiryDate": new_expiry.isoformat(),
                        "application_id": app.id,
                        "subtype": app.subtype,
                        "licenseNumber": prev_lic.license_number,
                    }
                    prev_lic.issued_by = payment.payer # Or a system user?
                    prev_lic.issued_date = issue_dt
                    prev_lic.expiry_date = new_expiry
                    prev_lic.data = merged_data
                    prev_lic.status = "active"
                    prev_lic.save()
                
                # Approve application
                app.approve()
                
                # Log the auto-approval
                ApplicationLog.objects.create(
                    application=app,
                    actor=payment.payer,
                    action="approved",
                    details="Auto-approved after successful renewal payment"
                )
                result["auto_approved"] = True
        except Exception as e:
            print(f"Auto-approval error: {str(e)}")
            
    except Exception as e:
        print(f"Error processing successful payment: {str(e)}")
    
    return result
