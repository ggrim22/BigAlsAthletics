from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404

from core.http import HTMXResponse
from .forms import ProductForm
from .models import Product, Size, Organization, Order, OrderItem

def index(request):
    products = Product.objects.filter(active=True)
    organizations = Organization.objects.filter(active=True)

    order_items = request.session.get("current_order_items", [])

    context = {
        "products": products,
        "order_items": order_items,
        "organizations": organizations,
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
        return HttpResponse(status=204)

    return HttpResponse(status=400)


def confirm_order(request):
    order_items = request.session.get("current_order_items", [])
    if not order_items:
        return redirect("order:index")

    if request.method == "POST":
        org_id = request.POST.get("organization")
        organization = get_object_or_404(Organization, id=org_id) if org_id else None

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
            organization=organization,
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

        return HTMXResponse(trigger="order-items-updated")

    return HTMXResponse()


def view_summary(request):
    order_items = request.session.get("current_order_items", [])
    organizations = Organization.objects.filter(active=True)

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
        "organizations": organizations,
        "total_cost": total_cost,
    })

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

@login_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        product.delete()
        return HTMXResponse(trigger="products-updated")

    context = {'product': product}
    return render(request, "order/modals/product-delete.html", context)


@login_required
def product_list(request):
    products = Product.objects.all()
    context = {
        "products": products,
    }
    return render(request, "order/partials/_product-list.html", context)

@login_required
def dashboard(request):
    products = Product.objects.all().order_by("name")
    context = {'products': products}
    return render(request, "order/product-dashboard.html", context)