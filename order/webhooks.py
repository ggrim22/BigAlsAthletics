import json
from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import stripe

from core import settings
from core.notify import send_alert
from core.settings import STRIPE_WEBHOOK_SECRET
from .models import Size
from .stripe_orders import create_order_from_checkout_session
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
        logger.error("Invalid payload in Stripe webhook")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature in Stripe webhook")
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
