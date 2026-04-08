from django.http import JsonResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from payments.models import Payment
from payments.services.chapa_service import ChapaService
from payments.utils import activate_license, process_successful_payment


def extract_chapa_id(checkout_url):
    if not checkout_url:
        return None

    # checkout_url looks like: https://checkout.chapa.co/checkout/payment/90PP41E3Wbxxxxx
    parts = checkout_url.rstrip("/").split("/")
    return parts[-1]


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def verify_payment(request, tx_ref):

    try:
        payment = Payment.objects.get(tx_ref=tx_ref)
    except Payment.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Payment not found"}, status=404)

    chapa = ChapaService.verify_payment(tx_ref)

    if chapa.get("status") == "success":

        payment.status = "success"
        payment.paid_at = timezone.now()

        # Resolve the official Chapa receipt URL
        final_receipt_url = None
        chapa_data = chapa.get("data", {})
        
        # LOG ENTIRE DATA FOR PRODUCTION DEBUGGING
        print(f"DEBUG: CHAPA VERIFY RESPONSE: {chapa_data}")
        
        # CHAPA RECEIPT URL RESOLUTION
        # Following Chapa Developer Docs & standard API response structure
        
        # 1. Highest Priority: Official 'receipt_url' from Chapa
        final_receipt_url = chapa_data.get("receipt_url")
        
        if not final_receipt_url:
            # 2. Extract internal reference using all known Chapa keys
            # Chapa uses 'chapa_reference' or 'reference' for their internal ID
            chapa_internal_ref = (
                chapa_data.get("chapa_reference") or 
                chapa_data.get("reference") or 
                chapa_data.get("id") or
                chapa_data.get("ref_id")
            )
            
            # 3. Fallback: Extraction from checkout_url (The hash used for payment)
            if (not chapa_internal_ref or chapa_internal_ref == payment.tx_ref) and payment.checkout_url:
                try:
                    chapa_internal_ref = payment.checkout_url.rstrip("/").split("/")[-1]
                except:
                    pass
            
            # Build the canonical link if we found an ID that looks like a Chapa hash
            # (Usually longer than 15 chars and doesn't start with our merchant prefix)
            if chapa_internal_ref and not str(chapa_internal_ref).startswith("license-"):
                final_receipt_url = f"https://chapa.link/payment/receipt/{chapa_internal_ref}"
            else:
                # Last resort: Try our tx_ref (per some docs)
                final_receipt_url = f"https://chapa.link/payment/receipt/{payment.tx_ref}"
        
        # SANITIZATION: Remove any spaces, quotes or backticks from the URL
        if final_receipt_url:
            final_receipt_url = str(final_receipt_url).strip().replace(" ", "").replace("`", "").replace("'", "").replace("\"", "")
        
        response_data = chapa_data.copy()
        response_data["receipt_url"] = final_receipt_url
        
        # Update DB
        if final_receipt_url:
            payment.receipt_url = final_receipt_url
            payment.save(update_fields=['receipt_url'])

        # Trigger post-payment logic (Auto-approval, etc.)
        post_payment_result = process_successful_payment(payment)

        # Cleanup response
        if isinstance(post_payment_result, dict):
            response_data.update(post_payment_result)

        if "checkout_url" in response_data:
            del response_data["checkout_url"]

        return JsonResponse({
            "status": "success",
            "message": "Payment verified successfully",
            "data": response_data
        })

    payment.status = "failed"
    payment.save()

    return JsonResponse({
        "status": "failed"
    })
