import json
import logging

from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import stripe

from core import settings
from core.decorators import get_client_ip
from core.notify import send_alert
from core.settings import STRIPE_WEBHOOK_SECRET
from .models import Size
from .stripe_orders import create_order_from_checkout_session

# Its own logger so webhook problems are attributable in logs and Sentry,
# rather than appearing to come from order.views.
logger = logging.getLogger(__name__)


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    client_ip = get_client_ip(request)

    if not sig_header:
        # Public URLs get scanned constantly. A POST with no Stripe-Signature
        # header did not come from Stripe, so this is noise rather than a fault
        # -- logged at WARNING so it does not raise a Sentry issue.
        logger.warning(
            "Webhook POST with no Stripe-Signature header from %s (%d bytes)",
            client_ip, len(payload),
        )
        return HttpResponse(status=400)

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.error(
            "Stripe webhook payload was not valid JSON: %d bytes from %s",
            len(payload), client_ip,
        )
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        # A genuine Stripe delivery that fails verification means the configured
        # signing secret does not match the endpoint, and real orders are being
        # dropped. Worth a Sentry issue.
        logger.error(
            "Stripe signature verification failed for a signed request from %s. "
            "STRIPE_WEBHOOK_SECRET is %s; confirm it matches this endpoint's "
            "signing secret and that test/live modes agree.",
            client_ip,
            "set" if STRIPE_WEBHOOK_SECRET else "EMPTY",
        )
        return HttpResponse(status=400)

    if event['type'] in ('checkout.session.completed', 'checkout.session.async_payment_succeeded'):
        session = event['data']['object']
        try:
            order, created = create_order_from_checkout_session(session['id'])
            if not created:
                return HttpResponse(status=200)

            total = sum(
                (item.product_cost or 0) * item.quantity for item in order.items.all()
            )
            items_list = []
            for order_item in order.items.all():
                size_display = dict(Size.choices).get(order_item.size, order_item.size) if order_item.size else 'N/A'
                back_name_text = f" (Back: {order_item.back_name})" if order_item.back_name else ""
                player_name_text = f"\n    Player: {order_item.player_name}" if order_item.player_name else ""
                items_list.append(
                    f"  - {order_item.product_name} - {order_item.product_color or 'N/A'}\n"
                    f"    Size: {size_display}\n"
                    f"    Quantity: {order_item.quantity}\n"
                    f"    Price: ${order_item.product_cost} each{back_name_text}"
                    f"{player_name_text}"
                )

            logger.info("Created order %s from Stripe session %s", order.id, session['id'])

            try:
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

            send_alert(
                summary=f"New order #{order.id} - ${total:.2f} - {order.customer_name or 'no name'}",
                urgent=True,
            )

        except Exception:
            logger.exception("Error creating order from Stripe session %s", session['id'])
            # The customer has already paid at this point, so this needs a human.
            send_alert(
                summary=f"PAID ORDER NOT RECORDED - Stripe session {session['id']}",
                detail=(
                    "A Stripe webhook reported a completed payment but the order "
                    "could not be saved.\n\n"
                    f"Session: {session['id']}\n"
                    "Check the Stripe dashboard for the payment and create the "
                    "order manually if needed."
                ),
                urgent=True,
            )
            return HttpResponse(status=500)

    return HttpResponse(status=200)
