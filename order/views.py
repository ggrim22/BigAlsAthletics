import json
import logging
from datetime import date
from decimal import Decimal
import polars as pl
import stripe

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Sum, Q
from django.http import HttpResponse, BadHeaderError
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from core import settings
from core.http import HTMXResponse
from core.utils import ExcelDownloadResponse
from .forms import ProductForm, CollectionForm, ColorForm, CategoryForm, ProductVariantForm, CollectionSelectForm, \
    CollectionFilterForm, ContactForm
from .models import Product, Size, Order, OrderItem, Collection, ProductColor, ProductCategory, ProductVariant

stripe.api_key = settings.STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)

def is_admin(user):
    return user.is_superuser


def index(request):
    form = CollectionSelectForm(request.POST or None)
    collection = None
    products = Product.objects.none()
    order_items = request.session.get("current_order_items", [])

    if request.method == "POST" and form.is_valid():
        selected_collection = form.cleaned_data["collection"]
        request.session["selected_collection_id"] = selected_collection.id

        products = Product.objects.filter(
            active=True, collection=selected_collection
        ).select_related("collection").prefetch_related(
            "category", "colors", "variants",
            "variants__category", "variants__color",
        ).order_by("name")

        if request.headers.get('HX-Request'):
            return render(request, "order/partials/_products.html", {
                "products": products,
                "collection": selected_collection
            })

        return redirect("order:index")

    collection_id = request.session.get("selected_collection_id")
    if is_admin(request.user):
        request.session.pop("selected_collection_id", None)
        products = Product.objects.filter(
            active=True, collection__active=True
        )
    elif collection_id:
        collection = get_object_or_404(Collection, pk=collection_id)
        products = Product.objects.filter(
            active=True, collection=collection
        )

    products = products.select_related("collection").prefetch_related(
        "category", "colors", "variants",
        "variants__category", "variants__color",
    ).order_by("name")

    context = {
        "form": form,
        "products": products,
        "order_items": order_items,
        "collection": collection,
    }

    if request.headers.get("HX-Request"):
        return render(request, "order/partials/_products.html", context)

    return render(request, "order/index.html", context)



def products(request, collection_id):
    selected_products = Product.objects.filter(collection=collection_id)
    context = {
        "selected_products": selected_products,
    }
    return render(request, "order/partials/_products.html", context)


def add_item(request):
    if request.method != "POST":
        return HttpResponse(status=400)

    product_id = request.POST.get("product")
    size = request.POST.get("size")
    quantity = int(request.POST.get("quantity", 1))
    color_id = request.POST.get("color")
    category_id = request.POST.get("category")
    back_name = request.POST.get("back_name", "").strip()

    product = get_object_or_404(Product, id=product_id)

    color_name = None
    if color_id:
        color = ProductColor.objects.filter(id=color_id).first()
        if color:
            color_name = color.name

    category_name = None
    price = Decimal("0.00")

    if category_id:
        category = ProductCategory.objects.filter(id=category_id).first()
        if category:
            category_name = category.name
            variant = product.variants.filter(category=category).first()
            if variant:
                price = variant.price

    if price == Decimal("0.00"):
        first_variant = product.variants.first()
        if first_variant:
            price = first_variant.price

        if size == Size.ADULT_2X or size == Size.ADULT_3X:
            price += 2

        if back_name:
            price += 2

        if size == Size.ADULT_4X:
            price += 3

    order_items = request.session.get("current_order_items", [])
    order_items.append({
        "product_id": product.id,
        "product_name": product.name,
        "size": size,
        "quantity": quantity,
        "color_id": color_id,
        "color_name": color_name,
        "category_id": category_id,
        "category_name": category_name,
        "price": str(price),
        "back_name": back_name,
    })
    request.session["current_order_items"] = order_items
    request.session.modified = True

    messages.success(request, "Added to cart")
    return HTMXResponse(trigger="items-updated")



# def confirm_order(request):
#     order_items = request.session.get("current_order_items", [])
#     if not order_items:
#         return redirect("order:index")
#
#     if request.method != "POST":
#         return redirect("order:index")
#
#     valid_items = []
#     for item in order_items:
#         product = Product.objects.filter(pk=item.get("product_id")).first()
#         if not product:
#             continue
#
#         back_name = item.get("back_name")
#         size = item.get("size")
#         if size not in product.available_sizes:
#             continue
#
#         price = Decimal(item.get("price", "0.00"))
#
#         if size == Size.ADULT_2X or size == Size.ADULT_3X:
#             price = price + 2
#
#         if back_name:
#             price = price + 2
#
#         if size == Size.ADULT_4X:
#             price = price + 3
#
#         valid_items.append({
#             "product": product,
#             "size": size,
#             "quantity": int(item.get("quantity", 1)),
#             "color_name": item.get("color_name"),
#             "category_name": item.get("category_name"),
#             "category_id": item.get("category_id"),
#             "price": price,
#             "back_name": back_name,
#         })
#
#     if not valid_items:
#         return redirect("order:index")
#
#     order = Order.objects.create(
#         customer_name=request.POST.get("customer_name", ""),
#         customer_email=request.POST.get("customer_email", ""),
#         customer_venmo=request.POST.get("customer_venmo", "")
#     )
#
#     total_cost = Decimal("0.00")
#     for it in valid_items:
#         OrderItem.objects.create(
#             order=order,
#             product=it["product"],
#             back_name=it["back_name"],
#             size=it["size"],
#             quantity=it["quantity"],
#             product_color=it.get("color_name"),
#             product_category=it.get("category_name"),
#             product_cost=it["price"],
#         )
#         total_cost += it["price"] * it["quantity"]
#
#     if "current_order_items" in request.session:
#         del request.session["current_order_items"]
#
#     return render(request, "order/confirmation.html", {"order": order, "total_cost": total_cost})


def confirm_order(request):
    order_items = request.session.get("current_order_items", [])
    if not order_items or request.method != "POST":
        return redirect("order:index")

    valid_items = []
    total_cost = Decimal("0.00")

    for item in order_items:
        product = Product.objects.filter(pk=item.get("product_id")).first()
        if not product:
            continue

        size = item.get("size")
        back_name = item.get("back_name")
        price = Decimal(item.get("price", "0.00"))

        if size in [Size.ADULT_2X, Size.ADULT_3X]:
            price += 2
        if size == Size.ADULT_4X:
            price += 3
        if back_name:
            price += 2

        valid_items.append({
            "product_id": product.id,
            "product_name": product.name,
            "size": size,
            "quantity": int(item.get("quantity", 1)),
            "color_name": item.get("color_name"),
            "category_name": item.get("category_name"),
            "category_id": item.get("category_id"),
            "price": str(price),
            "back_name": back_name,
        })

        total_cost += price * int(item.get("quantity", 1))

    if not valid_items:
        return redirect("order:index")

    customer_data = {
        "customer_name": request.POST.get("customer_name", ""),
        "customer_email": request.POST.get("customer_email", ""),
    }

    # CREATE PENDING ORDER IN DATABASE
    pending_order = Order.objects.create(
        customer_name=customer_data["customer_name"],
        customer_email=customer_data["customer_email"],
        pending_items=valid_items,  # Store items temporarily
        has_paid=False,
    )

    line_items = []
    for item in valid_items:
        product = Product.objects.get(pk=item["product_id"])
        line_items.append({
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "images": [request.build_absolute_uri(product.image.url)],
                    "name": item["product_name"],
                    "description": f"Size: {item['size']}, Color: {item['color_name'] or ''}, Custom Name: {item['back_name'] or ''}",
                },
                "unit_amount": int(Decimal(item["price"]) * 100),
            },
            "quantity": item["quantity"],
        })

    # SIMPLIFIED METADATA - ONLY PASS ORDER_ID
    metadata = {
        "order_id": pending_order.order_id,
    }

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        mode='payment',
        line_items=line_items,
        success_url=request.build_absolute_uri(reverse('order:payment-success')) + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=request.build_absolute_uri(reverse('order:payment-cancel')),
        metadata=metadata,
        customer_email=customer_data["customer_email"],
    )

    pending_order.stripe_session_id = checkout_session.id
    pending_order.save()

    request.session.pop("current_order_items", None)

    return redirect(checkout_session.url, code=303)


def delete_item(request, product_id, size):
    if request.method == "POST":
        order_items = request.session.get("current_order_items", [])

        for i, item in enumerate(order_items):
            if item["product_id"] == product_id and item["size"] == size:
                del order_items[i]
                break

        request.session["current_order_items"] = order_items
        request.session.modified = True

        return HTMXResponse(trigger="items-updated")

    return HTMXResponse()


def payment_success(request):
    session_id = request.GET.get("session_id")
    if not session_id:
        return redirect("order:index")

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        order_id = session.metadata.get('order_id')

        order = Order.objects.get(order_id=order_id)

        if order.pending_items and not order.has_paid:
            order.has_paid = True

            for item in order.pending_items:
                OrderItem.objects.create(
                    order=order,
                    product_id=item["product_id"],
                    product_name=item["product_name"],
                    size=item["size"],
                    quantity=item["quantity"],
                    product_color=item["color_name"],
                    product_category=item["category_name"],
                    category_id=item.get("category_id"),
                    product_cost=Decimal(item["price"]),
                    back_name=item.get("back_name", ""),
                )

            order.pending_items = None
            order.save()

        total_cost = Decimal("0.00")
        for item in order.items.all():
            price = item.product_cost or Decimal("0.00")

            if item.size in [Size.ADULT_2X, Size.ADULT_3X]:
                price += Decimal("2.00")
            elif item.size == Size.ADULT_4X:
                price += Decimal("3.00")

            if item.back_name:
                price += Decimal("2.00")

            total_cost += price * item.quantity

    except Exception as e:
        order = None
        total_cost = Decimal("0.00")

    return render(request, "order/payment-success.html", {
        "order": order,
        "total_cost": total_cost
    })

def payment_cancel(request):
    return render(request, "order/payment-cancel.html")

def view_summary(request):
    order_items = request.session.get("current_order_items", [])
    collections = Collection.objects.filter(active=True)

    total_cost = Decimal("0.00")
    cleaned_items = []

    for item in order_items:
        try:
            product = Product.objects.get(id=item["product_id"])
        except Product.DoesNotExist:
            continue

        price = Decimal(item.get("price", "0.00"))

        size = item.get("size")

        back_name = item.get("back_name")

        if size == Size.ADULT_2X or size == Size.ADULT_3X:
            price = price + 2

        if size == Size.ADULT_4X:
            price = price + 3

        if back_name:
            price = price + 2

        quantity = int(item.get("quantity", 1))
        total_cost += price * quantity

        cleaned_items.append({
            **item,
            "product": product,
            "product_color": item.get("color_name"),
            "product_category": item.get("category_name"),
            "product_price": price,
        })

    return render(request, "order/modals/order-summary.html", {
        "order_items": cleaned_items,
        "collections": collections,
        "total_cost": total_cost,
    })


def shopping_cart(request):
    order_items = request.session.get("current_order_items", [])
    collection_id = request.session.get("selected_collection_id")
    collection = None
    total_cost = Decimal("0.00")

    if collection_id:
        from .models import Collection
        collection = Collection.objects.filter(pk=collection_id).first()

    enriched_items = []
    for item in order_items:
        try:
            product = Product.objects.get(id=item["product_id"])
            price = Decimal(item.get("price", "0.00"))

            # Apply size upcharges
            size = item.get("size")
            if size in [Size.ADULT_2X, Size.ADULT_3X]:
                price += Decimal("2.00")
            elif size == Size.ADULT_4X:
                price += Decimal("3.00")

            # Apply back name upcharge
            if item.get("back_name"):
                price += Decimal("2.00")

            quantity = int(item.get("quantity", 1))
            total_cost += price * quantity

            enriched_items.append({
                **item,
                "product": product,
                "product_price": price,
            })
        except Product.DoesNotExist:
            continue

    context = {
        "order_items": enriched_items,
        "collection": collection,
        "total_cost": total_cost,
    }
    return render(request, "order/partials/_shopping-cart.html", context)

@user_passes_test(is_admin)
@login_required
def product_create(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return HTMXResponse(trigger="products-updated")
    else:
        form = ProductForm()

    print(form.errors)

    context = {'form': form}
    return render(request, "order/modals/product-create.html", context)


@user_passes_test(is_admin)
@login_required
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            return HTMXResponse(trigger="products-updated")
    else:
        form = ProductForm(instance=product)

    context = {'form': form}
    return render(request, "order/modals/product-update.html", context)


@user_passes_test(is_admin)
@login_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        product.delete()
        return HTMXResponse(trigger="products-updated")

    context = {'product': product}
    return render(request, "order/modals/product-delete.html", context)


@user_passes_test(is_admin)
@login_required
def product_list(request):
    products = Product.objects.all()
    context = {
        "products": products,
    }
    return render(request, "order/partials/_product-list.html", context)


@user_passes_test(is_admin)
@login_required
def product_dashboard(request):
    products = Product.objects.all().order_by("name")
    context = {'products': products}
    return render(request, "order/product-dashboard.html", context)


@user_passes_test(is_admin)
@login_required
def order_list(request):
    page = request.GET.get('page', 1)
    orders_per_page = 20

    all_orders = Order.objects.filter(archived=False).prefetch_related("items__product").order_by("-created_at")

    paginator = Paginator(all_orders, orders_per_page)
    orders = paginator.get_page(page)

    context = {
        'orders': orders,
        'has_next': orders.has_next(),
        'next_page': orders.next_page_number() if orders.has_next() else None,
    }

    if request.headers.get('HX-Request') and int(page) > 1:
        return render(request, "order/partials/_order-rows.html", context)

    return render(request, "order/partials/_order-list.html", context)

@user_passes_test(is_admin)
@login_required
def toggle_paid(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order.has_paid = "has_paid" in request.POST
    order.save()
    return HTMXResponse(trigger="order-items-updated")


@user_passes_test(is_admin)
@login_required
def order_dashboard(request):
    return render(request, "order/order-dashboard.html")


@user_passes_test(is_admin)
@login_required
def summary(request):
    size_codes = list(Size.values)
    collection_filter = request.GET.get("collection")

    summary_qs = (
        OrderItem.objects
        .filter(
            order__archived=False,
            product__collection__active=True
        )
        .values('product_name', 'product_category', 'product_color', 'product__collection')
        .annotate(
            **{
                code: Sum('quantity', filter=Q(size=code))
                for code in size_codes
            }
        )
    )

    if collection_filter:
        summary_qs = summary_qs.filter(product__collection=collection_filter)

    summary_qs = summary_qs.order_by('product_name', 'product_category', 'product_color')

    summary_table = []
    column_totals = [0] * len(size_codes)

    for row in summary_qs:
        size_quantities = []
        row_total = 0

        for i, code in enumerate(size_codes):
            qty = row.get(code) or 0
            size_quantities.append(qty)
            column_totals[i] += qty
            row_total += qty

        summary_table.append({
            'product_name': row['product_name'] or 'Deleted Product',
            'product_category': row['product_category'] or 'Unknown Category',
            'product_color': row['product_color'] or 'Unknown Color',
            'sizes': size_quantities,
            'row_total': row_total,
        })

    context = {
        "summary_table": summary_table,
        "size_codes": size_codes,
        "column_totals": column_totals,
        "filter_form": CollectionFilterForm(request.GET),
    }

    if request.headers.get("HX-Request"):
        return render(request, "order/partials/_summary-table.html", context)

    return render(request, "order/summary.html", context)


@user_passes_test(is_admin)
@login_required
def collection_dashboard(request):
    collections = Collection.objects.all()
    context = {'collections': collections}
    return render(request, "order/collection-dashboard.html", context)


@user_passes_test(is_admin)
@login_required
def collection_create(request):
    if request.method == "POST":
        form = CollectionForm(request.POST)
        if form.is_valid():
            Collection.objects.create(**form.cleaned_data)
            return HTMXResponse(trigger="collections-updated")
    else:
        form = CollectionForm()

    context = {'form': form}
    return render(request, "order/modals/collection-create.html", context)


@user_passes_test(is_admin)
@login_required
def collection_update(request, pk):
    collection = get_object_or_404(Collection, pk=pk)
    if request.method == "POST":
        form = CollectionForm(request.POST, instance=collection)
        if form.is_valid():
            form.save()
            return HTMXResponse(trigger="collections-updated")
    else:
        form = CollectionForm(instance=collection)

    context = {'form': form}
    return render(request, "order/modals/collection-update.html", context)


@user_passes_test(is_admin)
@login_required
def collection_delete(request, pk):
    collection = get_object_or_404(Collection, pk=pk)
    if request.method == "POST":
        collection.delete()
        return HTMXResponse(trigger="collections-updated")

    context = {'collection': collection}
    return render(request, "order/modals/collection-delete.html", context)


@user_passes_test(is_admin)
@login_required
def collection_list(request):
    collections = Collection.objects.all()
    context = {'collections': collections}
    return render(request, "order/partials/_collections-list.html", context)

def order_download(request):
    orders = Order.objects.prefetch_related("items")

    rows = []
    for order in orders:
        items_summary = []
        for item in order.items.all():
            items_summary.append(
                f"{item.product_name} - {item.product_category} ({item.size}){f' – {item.back_name}' if item.back_name else ''} x{item.quantity}, "
            )

        rows.append({
            "Customer Name": order.customer_name,
            "Customer Email": order.customer_email,
            "Venmo": order.customer_venmo,
            "Items": "\n".join(items_summary),
        })

    df = pl.DataFrame(rows)
    return ExcelDownloadResponse(df, "Big Al's Online Orders")


@user_passes_test(is_admin)
@login_required
def order_summary_download(request):
    size_codes = list(Size.values)
    size_labels = {code: label for code, label in Size.choices}

    collection_id = request.GET.get("collection")

    summary_qs = OrderItem.objects.all()

    if collection_id:
        summary_qs = summary_qs.filter(product__collection_id=collection_id)

    summary_qs = (
        summary_qs
        .values('product_name', 'product_category', 'product_color')
        .annotate(
            **{
                code: Sum('quantity', filter=Q(size=code))
                for code in size_codes
            }
        )
        .order_by('product_name', 'product_category', 'product_color')
    )

    summary_table = []
    column_totals = [0] * len(size_codes)

    for row in summary_qs:
        row_total = 0
        flattened_row = {
            "Product Name": row['product_name'] or 'Deleted Product',
            "Category": row['product_category'] or 'Unknown Category',
            "Color": row['product_color'] or 'Unknown Color',
        }

        for i, code in enumerate(size_codes):
            qty = row.get(code) or 0
            flattened_row[size_labels[code]] = qty
            column_totals[i] += qty
            row_total += qty

        flattened_row["Total Ordered"] = row_total
        summary_table.append(flattened_row)

    df = pl.DataFrame(summary_table)

    filename = f"Big Al's Order Summary - {date.today()}"
    if collection_id:
        collection_name = Collection.objects.get(id=collection_id).name
        filename += f" - {collection_name}"

    return ExcelDownloadResponse(df, filename)


@user_passes_test(is_admin)
@login_required
def product_color_create(request):
    if request.method == "POST":
        form = ColorForm(request.POST)
        if form.is_valid():
            ProductColor.objects.create(**form.cleaned_data)
            return HTMXResponse(trigger="product-color-updated")
    else:
        form = ColorForm()

    context = {'form': form}
    return render(request, "order/modals/product-color-create.html", context)


@user_passes_test(is_admin)
@login_required
def product_category_create(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            ProductCategory.objects.create(**form.cleaned_data)
            return HTMXResponse(trigger="product-category-updated")
    else:
        form = CategoryForm()

    context = {'form': form}
    return render(request, "order/modals/product-category-create.html", context)


@user_passes_test(is_admin)
@login_required
def add_or_update_variant(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    if request.method == "POST":
        form = ProductVariantForm(request.POST)
        if form.is_valid():
            variant, created = ProductVariant.objects.update_or_create(
                product=product,
                category=form.cleaned_data["category"],
                color=form.cleaned_data["color"],
                defaults={
                    "price": form.cleaned_data["price"],
                    "available_sizes": form.cleaned_data["available_sizes"],
                }
            )
            return HTMXResponse(trigger="variant-added")
    else:
        form = ProductVariantForm()

    return render(request, "order/modals/add-variant.html", {"form": form, "product": product})


def get_variant_sizes(request, product_id):
    category_id = request.GET.get('category')
    color_id = request.GET.get('color')

    product = get_object_or_404(Product, pk=product_id)

    variant_qs = ProductVariant.objects.filter(product=product)
    if category_id:
        variant_qs = variant_qs.filter(category_id=category_id)
    if color_id:
        variant_qs = variant_qs.filter(color_id=color_id)

    variant = variant_qs.first()

    if variant and variant.available_sizes:
        sizes = [(size_code, Size(size_code).label) for size_code in variant.available_sizes]
    else:
        sizes = product.get_available_sizes

    return render(request, "order/partials/_variant-info.html", {
        "product": product,
        "sizes": sizes,
        "current_size": None
    })


def get_variant_price(request, product_id):
    category_id = request.GET.get('category')
    color_id = request.GET.get('color')
    size = request.GET.get('size')
    back_name = request.GET.get('back_name')

    if not category_id or category_id == '':
        return HttpResponse('<i class="bi bi-currency-dollar"></i>0.00')

    variant_qs = ProductVariant.objects.filter(product_id=product_id)

    if category_id and category_id.isdigit():
        variant_qs = variant_qs.filter(category_id=int(category_id))

    if color_id and color_id.isdigit():
        variant_qs = variant_qs.filter(color_id=int(color_id))

    variant = variant_qs.first()

    if not variant and category_id and category_id.isdigit():
        variant_qs = ProductVariant.objects.filter(product_id=product_id, category_id=int(category_id))
        variant = variant_qs.first()

    if not variant:
        return HttpResponse('<i class="bi bi-currency-dollar"></i>0.00')

    price = variant.price

    if back_name:
        price += 2

    if size in [Size.ADULT_2X, Size.ADULT_3X]:
        price += 2
    elif size == Size.ADULT_4X:
        price += 3

    return HttpResponse(f'<i class="bi bi-currency-dollar"></i>{price:.2f}')


def about(request):
    return render(request, "order/about.html")



@user_passes_test(is_admin)
@login_required
def bulk_delete_orders(request):
    """Delete multiple orders at once"""
    if request.method == "POST":
        order_ids = request.POST.getlist('order_ids[]')
        if order_ids:
            Order.objects.filter(id__in=order_ids).delete()
            messages.success(request, f"Successfully deleted {len(order_ids)} order(s)")
        return HTMXResponse(trigger="order-items-updated")

    return HttpResponse(status=400)


@user_passes_test(is_admin)
@login_required
def bulk_archive_orders(request):
    """Archive multiple orders at once"""
    if request.method == "POST":
        order_ids = request.POST.getlist('order_ids[]')
        if order_ids:
            Order.objects.filter(id__in=order_ids).update(archived=True)
            messages.success(request, f"Successfully archived {len(order_ids)} order(s)")
        return HTMXResponse(trigger="order-items-updated")

    return HttpResponse(status=400)


@user_passes_test(is_admin)
@login_required
def archived_orders(request):
    """View archived orders"""
    orders = Order.objects.filter(archived=True).prefetch_related("items__product").order_by("-created_at")
    context = {'orders': orders, 'is_archived_view': True}
    return render(request, "order/order-archive.html", context)


@user_passes_test(is_admin)
@login_required
def restore_order(request, order_id):
    """Restore an archived order"""
    if request.method == "POST":
        order = get_object_or_404(Order, id=order_id)
        order.archived = False
        order.save()
        messages.success(request, "Order restored successfully")
        return HTMXResponse(trigger="order-items-updated")

    return HttpResponse(status=400)


def contact_page(request):

    if request.method == 'POST':
        form = ContactForm(request.POST)

        if form.is_valid():
            user_email = form.cleaned_data['email']
            user_message = form.cleaned_data['message']

            subject = f"New Contact Form Submission from {user_email}"
            message = f"""
                    You have received a new message from the Big Al's Athletics contact form.
                    
                    From: {user_email}
                    
                    Message:
                    {user_message}
                    
                    ---
                    This message was sent via the contact form on your website.
                                """

            try:
                # Send email
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.CONTACT_EMAIL],
                    fail_silently=False,
                )

                messages.success(request, 'Your message has been sent successfully! We\'ll get back to you soon.')
                logger.info(f"Contact form submitted by {user_email}")
                return redirect('order:contact')

            except BadHeaderError:
                messages.error(request, 'Invalid header found. Please try again.')
                logger.error(f"Bad header in contact form from {user_email}")

            except Exception as e:
                messages.error(request, 'An error occurred while sending your message. Please try again later.')
                logger.error(f"Error sending contact email: {str(e)}")

    else:
        form = ContactForm()

    return render(request, 'order/contact.html', {'form': form})