import json
from decimal import Decimal
from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import stripe

from core import settings
from core.settings import STRIPE_WEBHOOK_SECRET
from .models import Order, OrderItem, Product, Size
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

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']

        # Get order_id from metadata instead of parsing order_items JSON
        order_id = session['metadata'].get('order_id')

        if not order_id:
            logger.error(f"No order_id found in session {session['id']} metadata")
            return HttpResponse(status=400)

        try:
            order = Order.objects.get(order_id=order_id)

            if order.has_paid and not order.pending_items:
                logger.info(f"Order {order.id} already processed, skipping webhook")
                return HttpResponse(status=200)

            order.has_paid = True

            total = Decimal('0.00')
            items_list = []

            if order.pending_items:
                for item_data in order.pending_items:
                    product = Product.objects.filter(pk=item_data.get("product_id")).first()
                    if not product:
                        logger.warning(f"Product {item_data.get('product_id')} not found for order")
                        continue

                    order_item = OrderItem.objects.create(
                        order=order,
                        product=product,
                        back_name=item_data.get("back_name", ""),
                        size=item_data.get("size"),
                        quantity=item_data.get("quantity", 1),
                        product_color=item_data.get("color_name"),
                        product_category=item_data.get("category_name"),
                        product_cost=Decimal(item_data.get("price", "0.00")),
                        category_id=item_data.get("category_id"),
                    )

                    item_total = order_item.product_cost * order_item.quantity
                    total += item_total

                    size_display = dict(Size.choices).get(order_item.size,
                                                          order_item.size) if order_item.size else 'N/A'
                    back_name_text = f" (Back: {order_item.back_name})" if order_item.back_name else ""

                    items_list.append(
                        f"  - {order_item.product_name} - {order_item.product_color or 'N/A'}\n"
                        f"    Category: {order_item.product_category or 'N/A'}\n"
                        f"    Size: {size_display}\n"
                        f"    Quantity: {order_item.quantity}\n"
                        f"    Price: ${order_item.product_cost} each{back_name_text}"
                    )

                order.pending_items = None

            order.save()

            logger.info(f"Successfully processed order {order.id} from Stripe session {session['id']}")

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

        except Order.DoesNotExist:
            logger.error(f"Order with order_id {order_id} not found for session {session['id']}")
            return HttpResponse(status=404)
        except Exception as e:
            logger.error(f"Error processing order from Stripe session {session['id']}: {str(e)}")
            return HttpResponse(status=500)

    return HttpResponse(status=200)