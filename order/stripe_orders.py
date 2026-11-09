"""Create local orders from completed Stripe Checkout sessions."""

from decimal import Decimal

import stripe
from django.db import transaction

from core import settings
from .models import Order, OrderItem, Product


stripe.api_key = settings.STRIPE_SECRET_KEY


def _value(value, key, default=None):
    """Read a field from Stripe objects as well as ordinary test dictionaries."""
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _metadata(value):
    metadata = _value(value, "metadata", {}) or {}
    if isinstance(metadata, dict):
        return metadata
    # stripe-python 16 exposes nested API data as StripeObject instances.
    # They deliberately do not implement dict methods such as ``.get()``.
    return metadata.to_dict() if hasattr(metadata, "to_dict") else {}


def create_order_from_checkout_session(session_id):
    """Persist a paid Checkout Session and its line items exactly once.

    The success redirect and Stripe webhook can arrive in either order.  Looking
    up the session ID first keeps both paths idempotent; the atomic block also
    prevents a half-created order from being saved when Stripe data is invalid
    or unavailable.
    """
    existing_order = Order.objects.filter(stripe_session_id=session_id).first()
    if existing_order:
        return existing_order, False

    checkout_session = stripe.checkout.Session.retrieve(session_id)
    if _value(checkout_session, "payment_status") != "paid":
        raise ValueError("Checkout Session has not been paid")

    session_metadata = _metadata(checkout_session)

    with transaction.atomic():
        # Check again after acquiring a database lock.  The webhook and the
        # customer's browser commonly reach this code at almost the same time.
        existing_order = (
            Order.objects.select_for_update()
            .filter(stripe_session_id=session_id)
            .first()
        )
        if existing_order:
            return existing_order, False

        order = Order.objects.create(
            customer_name=session_metadata.get("customer_name", ""),
            customer_email=session_metadata.get("customer_email", ""),
            stripe_session_id=session_id,
            has_paid=True,
        )

        line_items = stripe.checkout.Session.list_line_items(
            session_id,
            limit=100,
            expand=["data.price.product"],
        )

        for line_item in _value(line_items, "data", []):
            price = _value(line_item, "price")
            stripe_product = _value(price, "product")
            product_metadata = _metadata(stripe_product)

            product_name = _value(stripe_product, "name", "") or _value(
                line_item, "description", ""
            )
            product_id = product_metadata.get("product_id")
            product = Product.objects.filter(pk=product_id).first() if product_id else None

            quantity = int(_value(line_item, "quantity", 1) or 1)
            amount_total = Decimal(str(_value(line_item, "amount_total", 0)))
            unit_price = amount_total / Decimal("100") / quantity

            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product_name,
                size=product_metadata.get("size", ""),
                quantity=quantity,
                product_color=product_metadata.get("color", ""),
                product_category=product_metadata.get("category", ""),
                product_cost=unit_price,
                back_name=product_metadata.get("back_name", ""),
            )

    return order, True
