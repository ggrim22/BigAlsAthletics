import json
import stripe
from decimal import Decimal
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Order, OrderItem, Product

stripe.api_key = settings.STRIPE_SECRET_KEY


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']

        order = Order.objects.create(
            customer_name=session['metadata'].get('customer_name', ''),
            customer_email=session['metadata'].get('customer_email', ''),
            customer_venmo=session['metadata'].get('customer_venmo', ''),
            has_paid=True
        )

        order_items_json = session['metadata'].get('order_items', '[]')
        order_items = json.loads(order_items_json)

        for item in order_items:
            product = Product.objects.filter(pk=item['product_id']).first()
            if product:
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    back_name=item.get('back_name'),
                    size=item.get('size'),
                    quantity=item.get('quantity', 1),
                    product_color=item.get('color_name'),
                    product_category=item.get('category_name'),
                    product_cost=Decimal(item.get('price', '0.00')),
                )

    return HttpResponse(status=200)