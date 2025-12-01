from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import stripe

from core.settings import STRIPE_WEBHOOK_SECRET
from .models import Order

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        order_id = session['metadata'].get('order_id')
        if order_id:
            try:
                order = Order.objects.get(id=order_id)
                order.has_paid = True
                order.save()
            except Order.DoesNotExist:
                pass

    return HttpResponse(status=200)
