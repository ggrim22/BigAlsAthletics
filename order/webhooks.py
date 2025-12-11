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

        customer_name = session['metadata'].get('customer_name', '')
        customer_email = session['metadata'].get('customer_email', '')

        try:
            order = Order.objects.create(
                customer_name=customer_name,
                customer_email=customer_email,
                stripe_session_id=session['id'],
                has_paid=True,
            )

            line_items = stripe.checkout.Session.list_line_items(
                session['id'],
                limit=100,
                expand=['data.price.product']
            )

            total = Decimal('0.00')
            items_list = []

            for line_item in line_items.data:
                product_name = ""
                metadata = {}

                if hasattr(line_item.price, 'product') and isinstance(line_item.price.product, stripe.Product):
                    product_name = line_item.price.product.name
                    metadata = line_item.price.product.metadata if hasattr(line_item.price.product, 'metadata') else {}

                size = metadata.get('size', '')
                color = metadata.get('color', '')
                back_name = metadata.get('back_name', '')
                category = metadata.get('category', '')
                product_id = metadata.get('product_id', '')  # ADD THIS - we need to store product_id in metadata

                unit_price = Decimal(line_item.amount_total) / 100 / line_item.quantity

                product = None
                if product_id:
                    product = Product.objects.filter(pk=product_id).first()

                order_item = OrderItem.objects.create(
                    order=order,
                    product=product,
                    product_name=product_name,
                    size=size,
                    quantity=line_item.quantity,
                    product_color=color,
                    product_category=category,
                    product_cost=unit_price,
                    back_name=back_name if back_name else "",
                )

                item_total = order_item.product_cost * order_item.quantity
                total += item_total

                size_display = dict(Size.choices).get(order_item.size, order_item.size) if order_item.size else 'N/A'
                back_name_text = f" (Back: {order_item.back_name})" if order_item.back_name else ""

                items_list.append(
                    f"  - {order_item.product_name} - {order_item.product_color or 'N/A'}\n"
                    f"    Size: {size_display}\n"
                    f"    Quantity: {order_item.quantity}\n"
                    f"    Price: ${order_item.product_cost} each{back_name_text}"
                )

            logger.info(f"Successfully created order {order.id} from Stripe session {session['id']}")

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

        except Exception as e:
            logger.error(f"Error creating order from Stripe session {session['id']}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return HttpResponse(status=500)

    return HttpResponse(status=200)