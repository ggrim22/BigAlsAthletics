from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404

from core.http import HTMXResponse
from .forms import ProductForm, CollectionForm
from .models import Product, Size, Order, OrderItem, Collection


def is_admin(user):
    return user.is_superuser

def index(request):
    products = Product.objects.filter(active=True).prefetch_related("available_sizes")
    collections = Collection.objects.filter(active=True)

    order_items = request.session.get("current_order_items", [])

    context = {
        "products": products,
        "order_items": order_items,
        "collections": collections,
    }
    return render(request, "order/index.html", context)


def add_item(request):
    if request.method == "POST":
        product_id = request.POST.get("product")
        size_id = request.POST.get("size")
        quantity = int(request.POST.get("quantity", 1))

        product = get_object_or_404(Product, id=product_id)
        size = get_object_or_404(Size, id=size_id)

        order_items = request.session.get("current_order_items", [])
        order_items.append({
            "product_name": product.name,
            "size_code": size.code,
            "quantity": quantity,
            "product_id": product.id,
            "size_id": size.id
        })
        request.session["current_order_items"] = order_items
        request.session.modified = True

        messages.success(request, "Item added")
        return HTMXResponse(trigger='items-updated')

    return HttpResponse(status=400)


def confirm_order(request):
    order_items = request.session.get("current_order_items", [])
    if not order_items:
        return redirect("order:index")

    if request.method == "POST":
        collection_id = request.POST.get("collection")
        collection = get_object_or_404(Collection, id=collection_id) if collection_id else None

        valid_items = []
        removed_items = []

        for item in order_items:
            product_id = item.get("product_id")
            size_id = item.get("size_id")

            product_exists = Product.objects.filter(pk=product_id).exists()
            size_exists = Size.objects.filter(pk=size_id).exists()

            if product_exists and size_exists:
                valid_items.append(item)
            else:
                removed_items.append(item)

        request.session["current_order_items"] = valid_items


        if not valid_items:
            return redirect("order:index")

        order = Order.objects.create(
            collection=collection,
            customer_name=request.POST.get("customer_name", ""),
            customer_email=request.POST.get("customer_email", ""),
            customer_venmo=request.POST.get("customer_venmo", "")
        )

        for item in valid_items:
            OrderItem.objects.create(
                order=order,
                product_id=item["product_id"],
                size_id=item["size_id"],
                quantity=item["quantity"]
            )

        del request.session["current_order_items"]

        total_cost = Decimal("0.00")
        cleaned_items = []

        for item in order_items:
            try:
                product = Product.objects.get(id=item["product_id"])
                total_cost += item["quantity"] * product.cost
                cleaned_items.append({
                    **item,
                    "product": product,
                })
            except Product.DoesNotExist:
                continue

        return render(request, "order/confirmation.html", {"order": order, 'total_cost': total_cost})

    return redirect("order:index")

def delete_item(request, product_id, size_id):
    if request.method == "POST":
        order_items = request.session.get("current_order_items", [])
        new_items = [
            item for item in order_items
            if not (item["product_id"] == product_id and item["size_id"] == size_id)
        ]
        request.session["current_order_items"] = new_items
        request.session.modified = True

        return HTMXResponse(trigger="items-updated")

    return HTMXResponse()


def view_summary(request):
    order_items = request.session.get("current_order_items", [])
    collections = Collection.objects.filter(active=True)

    total_cost = Decimal("0.00")
    cleaned_items = []

    for item in order_items:
        try:
            product = Product.objects.get(id=item["product_id"])
            total_cost += item["quantity"] * product.cost
            cleaned_items.append({
                **item,
                "product": product,
            })
        except Product.DoesNotExist:
            continue

    return render(request, "order/modals/order-summary.html", {
        "order_items": cleaned_items,
        "collections": collections,
        "total_cost": total_cost,
    })


def shopping_cart(request):
    order_items = request.session.get("current_order_items", [])
    context = {'order_items': order_items}
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
    orders = Order.objects.prefetch_related("items__product", "items__size").all().order_by("-created_at")
    context = {'orders': orders}
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
    orders = Order.objects.all()
    context = {'orders': orders}
    return render(request, "order/order-dashboard.html", context)


@user_passes_test(is_admin)
@login_required
def summary(request):
    size_order = ['XS', 'YS', 'YM', 'YL', 'YXL', 'AS', 'AM', 'AL', 'AXL', '2X', '3X', '4X']

    size_codes = list(
        OrderItem.objects
        .exclude(size_code__isnull=True)
        .values_list('size_code', flat=True)
        .distinct()
    )

    size_codes = [code for code in size_order if code in size_codes]

    summary_qs = OrderItem.objects.values('product_name')

    for code in size_codes:
        summary_qs = summary_qs.annotate(
            **{code: Sum('quantity', filter=Q(size_code=code))}
        )

    summary_qs = summary_qs.order_by('product_name')

    summary_table = []
    column_totals = [0] * len(size_codes)

    for row in summary_qs:
        sizes = []
        row_total = 0
        for i, code in enumerate(size_codes):
            qty = row.get(code) or 0
            sizes.append(qty)
            row_total += qty
            column_totals[i] += qty
        summary_table.append({
            'product_name': row['product_name'] or 'Deleted Product',
            'sizes': sizes,
            'row_total': row_total,
        })

    grand_total = sum(column_totals)

    return render(request, 'order/summary.html', {
        'summary_table': summary_table,
        'size_codes': size_codes,
        'column_totals': column_totals,
        'grand_total': grand_total,
    })


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