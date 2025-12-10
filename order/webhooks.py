from decimal import Decimal

from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import stripe

from core import settings
from core.settings import STRIPE_WEBHOOK_SECRET
from .models import Order, Size
from .views import logger


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

                try:
                    items_list = []
                    total = Decimal('0.00')

                    for item in order.items.all():
                        item_total = (item.product_cost or Decimal('0.00')) * item.quantity
                        total += item_total

                        size_display = dict(Size.choices).get(item.size, item.size) if item.size else 'N/A'
                        back_name_text = f" (Back: {item.back_name})" if item.back_name else ""

                        items_list.append(
                            f"  - {item.product_name} - {item.product_color or 'N/A'}\n"
                            f"    Category: {item.product_category or 'N/A'}\n"
                            f"    Size: {size_display}\n"
                            f"    Quantity: {item.quantity}\n"
                            f"    Price: ${item.product_cost or '0.00'} each{back_name_text}"
                        )

                    items_summary = "\n\n".join(items_list) if items_list else "No items"

                    subject = f"New Order #{order.id} - Big Al's Athletics"
                    message = f"""
                        A new order has been received and paid!
    
                        Order ID: #{order.id}
                        Customer Name: {order.customer_name}
                        Email: {order.customer_email}
                        Order Date: {order.created_at.strftime('%B %d, %Y at %I:%M %p')}
                        
                        Order Items:
                        {items_summary}
                        
                        Total: ${total:.2f}
                        
                        ---
                        This notification was sent automatically from your website.
                    """

                    send_mail(
                        subject=subject,
                        message=message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[settings.CONTACT_EMAIL],
                        fail_silently=False,
                    )
                    logger.info(f"Order notification email sent for order {order.id}")

                except Exception as e:
                    logger.error(f"Error sending order notification email: {str(e)}")

            except Order.DoesNotExist:
                pass

    return HttpResponse(status=200)
