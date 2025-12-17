"""
Shared pytest fixtures for Django testing
"""
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from order.models import (
    Product, ProductCategory, ProductColor, Collection,
    Order, OrderItem, Size, ProductVariant
)

User = get_user_model()


@pytest.fixture
def request_factory():
    """Provides Django RequestFactory for creating mock requests"""
    return RequestFactory()


@pytest.fixture
def admin_user(db):
    """Creates an admin user for testing admin views"""
    return User.objects.create_superuser(
        username='admin',
        email='admin@test.com',
        password='adminpass123'
    )


@pytest.fixture
def regular_user(db):
    """Creates a regular (non-admin) user"""
    return User.objects.create_user(
        username='user',
        email='user@test.com',
        password='userpass123'
    )


@pytest.fixture
def product_category(db):
    """Creates a test product category"""
    return ProductCategory.objects.create(
        name='T-Shirt',
        active=True
    )


@pytest.fixture
def product_category_hoodie(db):
    """Creates a hoodie category"""
    return ProductCategory.objects.create(
        name='Hoodie',
        active=True
    )


@pytest.fixture
def product_color(db):
    """Creates a test product color"""
    return ProductColor.objects.create(name='Red')


@pytest.fixture
def product_color_blue(db):
    """Creates a blue color"""
    return ProductColor.objects.create(name='Blue')


@pytest.fixture
def collection(db):
    """Creates a test collection"""
    return Collection.objects.create(
        name='Spring 2024',
        active=True
    )


@pytest.fixture
def inactive_collection(db):
    """Creates an inactive collection"""
    return Collection.objects.create(
        name='Winter 2023',
        active=False
    )


@pytest.fixture
def product(db, collection, product_category, product_color):
    """Creates a test product with image"""
    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image
    from io import BytesIO

    # Create a simple test image
    img = Image.new('RGB', (344, 250), color='red')
    img_io = BytesIO()
    img.save(img_io, format='JPEG')
    img_io.seek(0)

    product = Product.objects.create(
        name='Test Shirt',
        collection=collection,
        image=SimpleUploadedFile('test.jpg', img_io.read(), content_type='image/jpeg'),
        available_sizes=[Size.ADULT_M, Size.ADULT_L, Size.ADULT_XL],
        has_back_name=True,
        active=True
    )
    product.category.add(product_category)
    product.colors.add(product_color)
    return product


@pytest.fixture
def product_variant(db, product, product_category, product_color):
    """Creates a test product variant"""
    return ProductVariant.objects.create(
        product=product,
        category=product_category,
        color=product_color,
        price=Decimal('25.00'),
        available_sizes=[Size.ADULT_M, Size.ADULT_L, Size.ADULT_XL]
    )


@pytest.fixture
def order(db):
    """Creates a test order"""
    return Order.objects.create(
        customer_name='John Doe',
        customer_email='john@test.com',
        customer_venmo='@johndoe',
        has_paid=False,
        archived=False
    )


@pytest.fixture
def paid_order(db):
    """Creates a paid order"""
    return Order.objects.create(
        customer_name='Jane Smith',
        customer_email='jane@test.com',
        has_paid=True,
        stripe_session_id='sess_test123',
        archived=False
    )


@pytest.fixture
def order_item(db, order, product, product_category):
    """Creates a test order item"""
    return OrderItem.objects.create(
        order=order,
        product=product,
        product_name=product.name,
        product_color='Red',
        product_category=product_category.name,
        product_cost=Decimal('25.00'),
        size=Size.ADULT_L,
        quantity=2,
        back_name='SMITH'
    )


@pytest.fixture
def multiple_products(db, collection, product_category):
    """Creates multiple products for testing lists"""
    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image
    from io import BytesIO

    products = []
    for i in range(5):
        img = Image.new('RGB', (344, 250), color='blue')
        img_io = BytesIO()
        img.save(img_io, format='JPEG')
        img_io.seek(0)

        product = Product.objects.create(
            name=f'Product {i + 1}',
            collection=collection,
            image=SimpleUploadedFile(f'test{i}.jpg', img_io.read(), content_type='image/jpeg'),
            available_sizes=[Size.ADULT_M, Size.ADULT_L],
            active=True
        )
        product.category.add(product_category)
        products.append(product)

    return products


@pytest.fixture
def session_with_items(db, product):
    """Creates a session dict with order items"""
    return {
        'current_order_items': [
            {
                'product_id': product.id,
                'product_name': product.name,
                'size': Size.ADULT_L,
                'quantity': 1,
                'color_id': None,
                'color_name': 'Red',
                'category_id': None,
                'category_name': 'T-Shirt',
                'price': '25.00',
                'back_name': ''
            }
        ],
        'selected_collection_id': product.collection.id
    }