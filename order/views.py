from datetime import date
from decimal import Decimal
import polars as pl


from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404

from core.http import HTMXResponse
from core.utils import ExcelDownloadResponse
from .forms import ProductForm, CollectionForm, ColorForm, CategoryForm, ProductVariantForm
from .models import Product, Size, Order, OrderItem, Collection, ProductColor, ProductCategory, ProductVariant


def is_admin(user):
    return user.is_superuser

def index(request):
    products = Product.objects.filter(active=True)
    collections = Collection.objects.filter(active=True)

    order_items = request.session.get("current_order_items", [])

    context = {
        "products": products,
        "order_items": order_items,
        "collections": collections,
    }
    return render(request, "order/index.html", context)

def get_variant_price(request, product_id):
    category_id = request.GET.get('category')
    if category_id:
        variant = ProductVariant.objects.filter(product_id=product_id, category_id=category_id).first()
        if variant:
            return HttpResponse(f"${variant.price:.2f}")
    return HttpResponse("$0.00")


def add_item(request):
    if request.method == "POST":
        product_id = request.POST.get("product")
        size = request.POST.get("size")
        quantity = int(request.POST.get("quantity", 1))
        color_id = request.POST.get("color")
        category_id = request.POST.get("category")

        product = get_object_or_404(Product, id=product_id)

        color_name = None
        if color_id:
            color_obj = ProductColor.objects.filter(id=color_id).first()
            if color_obj:
                color_name = color_obj.name

        category_name = None
        price = Decimal("0.00")

        if category_id:
            category_obj = ProductCategory.objects.filter(id=category_id).first()
            if category_obj:
                category_name = category_obj.name
                variant = product.variants.filter(category=category_obj).first()
                if variant:
                    price = variant.price
        else:
            first_variant = product.variants.first()
            if first_variant:
                price = first_variant.price

        order_items = request.session.get("current_order_items", [])
        order_items.append({
            "product_name": product.name,
            "size": size,
            "quantity": quantity,
            "product_id": product.id,
            "color": color_name,
            "category": category_name,
            "price": str(price),
        })
        request.session["current_order_items"] = order_items
        request.session.modified = True

        messages.success(request, "Added to cart")
        return HTMXResponse(trigger='items-updated')

    return HttpResponse(status=400)


def confirm_order(request):
    order_items = request.session.get("current_order_items", [])
    if not order_items:
        return redirect("order:index")

    if request.method == "POST":
        valid_items = []

        for item in order_items:
            product_id = item.get("product_id")
            try:
                product = Product.objects.get(pk=product_id)
            except Product.DoesNotExist:
                continue

            if item.get("size") in product.available_sizes:
                valid_items.append({
                    "product": product,
                    "size": item.get("size"),
                    "quantity": item.get("quantity", 1),
                    "color": item.get("color"),
                    "category": int(item.get("category")),
                })

        request.session["current_order_items"] = valid_items

        if not valid_items:
            return redirect("order:index")

        order = Order.objects.create(
            customer_name=request.POST.get("customer_name", ""),
            customer_email=request.POST.get("customer_email", ""),
            customer_venmo=request.POST.get("customer_venmo", "")
        )

        total_cost = Decimal("0.00")

        for item in valid_items:
            variant = item["product"].variants.filter(category_id=item["category"]).first()
            price = variant.price if variant else Decimal("0.00")

            OrderItem.objects.create(
                order=order,
                product=item["product"],
                size=item["size"],
                quantity=item["quantity"],
                product_color=item.get("color"),
                product_category=item.get("category"),
                product_cost=price
            )

            total_cost += item["quantity"] * price

        del request.session["current_order_items"]

        return render(request, "order/confirmation.html", {"order": order, "total_cost": total_cost})

    return redirect("order:index")

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


def view_summary(request):
    order_items = request.session.get("current_order_items", [])
    collections = Collection.objects.filter(active=True)

    total_cost = Decimal("0.00")
    cleaned_items = []

    for item in order_items:
        try:
            product = Product.objects.get(id=item["product_id"])

            price = Decimal(item.get("price", "0.00"))

            total_cost += price * item.get("quantity", 1)

            cleaned_items.append({
                **item,
                "product": product,
                "product_color": item.get("color"),
                "product_category": item.get("category"),
                "price": price,
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
    orders = Order.objects.prefetch_related("items__product").order_by("-created_at")
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
    size_codes = list(Size.values)

    summary_qs = OrderItem.objects.values('product_name').annotate(
        **{
            code: Sum('quantity', filter=Q(size=code))
            for code in size_codes
        }
    ).order_by('product_name')

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
            'sizes': size_quantities,
            'row_total': row_total,
        })

    return render(request, 'order/summary.html', {
        'summary_table': summary_table,
        'size_codes': size_codes,
        'column_totals': column_totals,
    })

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
                f"{item.product_name} ({item.size}) x{item.quantity}, "
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

    summary_qs = OrderItem.objects.values('product_name').annotate(
        **{
            code: Sum('quantity', filter=Q(size=code))
            for code in size_codes
        }
    ).order_by('product_name')

    summary_table = []
    column_totals = [0] * len(size_codes)

    for row in summary_qs:
        row_total = 0
        flattened_row = {
            "Product Name": row['product_name'] or 'Deleted Product',
        }

        for i, code in enumerate(size_codes):
            qty = row.get(code) or 0
            flattened_row[size_labels[code]] = qty
            column_totals[i] += qty
            row_total += qty

        flattened_row["Total Ordered"] = row_total
        summary_table.append(flattened_row)

    df = pl.DataFrame(summary_table)

    return ExcelDownloadResponse(
        df,
        f"Big Al's Order Summary - {date.today()}"
    )

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
                defaults={"price": form.cleaned_data["price"]}
            )
            return HTMXResponse(trigger="variant-added")
    else:
        form = ProductVariantForm()

    return render(request, "order/modals/add-variant.html", {"form": form, "product": product})
