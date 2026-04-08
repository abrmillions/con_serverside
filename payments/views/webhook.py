import json
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from payments.models import Payment
from payments.utils import activate_license, process_successful_payment


@csrf_exempt
def chapa_webhook(request):

    if request.method == "POST":
        try:
            # Chapa typically sends JSON
            data = json.loads(request.body)
        except json.JSONDecodeError:
            # Fallback to POST data
            data = request.POST

        tx_ref = data.get("tx_ref")
        status = data.get("status")

        try:
            payment = Payment.objects.get(tx_ref=tx_ref)

            if status == "success":
                payment.status = "success"
                payment.save()

                activate_license(payment.payer)
                process_successful_payment(payment)

        except Payment.DoesNotExist:
            pass

    return JsonResponse({"message": "Webhook received"})
