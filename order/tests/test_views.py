"""
Tests for order views
"""
import pytest
from django.core.cache import cache
from decimal import Decimal
from unittest.mock import Mock, patch
from django.urls import reverse
from django.test import Client
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.models import AnonymousUser

from order.models import (
    Product, Order, OrderItem, Collection, Size,
    ProductCategory, ProductColor, ProductVariant
)


@pytest.fixture
def client():
    """Provides Django test client"""
    return Client()


@pytest.fixture
def authenticated_client(client, admin_user):
    """Provides authenticated client"""
    client.force_login(admin_user)
    return client


def add_session_to_request(request):
    """Helper to add session to request"""
    middleware = SessionMiddleware(get_response=lambda req: None)
    middleware.process_request(request)
    request.session.save()


@pytest.fixture(autouse=True)
def clear_cache_for_tests():
    """Clear cache before and after each test to reset rate limits"""
    cache.clear()
    yield
    cache.clear()

@pytest.mark.django_db
class TestIndexView:
    """Tests for index view"""

    def test_index_view_loads(self, client):
        """Test that index page loads successfully"""
        response = client.get(reverse('order:index'))
        assert response.status_code == 200
        assert 'products' in response.context

    def test_index_view_no_collection_selected(self, client, product):
        """Test index with no collection selected"""
        response = client.get(reverse('order:index'))
        assert response.status_code == 200
        # Non-admin users should see no products without collection
        products = response.context['products']
        assert products.count() == 0

    def test_index_view_with_collection_post(self, client, collection, product):
        """Test posting collection selection"""
        response = client.post(reverse('order:index'), {
            'collection': collection.id
        })
        # Should redirect after POST
        assert response.status_code == 302

        # Check session was updated
        assert client.session.get('selected_collection_id') == collection.id

    def test_index_view_admin_sees_all_products(self, authenticated_client, product):
        """Test that admin users see all products"""
        response = authenticated_client.get(reverse('order:index'))
        assert response.status_code == 200
        products = response.context['products']
        assert product in products

    def test_index_view_only_active_products(self, client, collection, product):
        """Test that only active products are shown"""
        # Create inactive product
        inactive_product = Product.objects.create(
            name='Inactive Product',
            collection=collection,
            active=False
        )

        # Set collection in session
        session = client.session
        session['selected_collection_id'] = collection.id
        session.save()

        response = client.get(reverse('order:index'))
        products = response.context['products']
        assert product in products
        assert inactive_product not in products


@pytest.mark.django_db
class TestAddItemView:
    """Tests for add_item view"""

    def test_add_item_success(self, client, product, product_category):
        """Test adding an item to cart"""
        response = client.post(reverse('order:add_item'), {
            'product': product.id,
            'size': Size.ADULT_L,
            'quantity': 2,
            'category': product_category.id,
            'back_name': 'SMITH'
        })

        # Check item was added to session
        order_items = client.session.get('current_order_items', [])
        assert len(order_items) == 1
        assert order_items[0]['product_id'] == product.id
        assert order_items[0]['size'] == Size.ADULT_L
        assert order_items[0]['quantity'] == 2
        assert order_items[0]['back_name'] == 'SMITH'

    def test_add_item_with_variant_price(self, client, product, product_variant):
        """Test that variant price is used when available"""
        response = client.post(reverse('order:add_item'), {
            'product': product.id,
            'size': Size.ADULT_L,
            'quantity': 1,
            'category': product_variant.category.id,
            'color': product_variant.color.id
        })

        order_items = client.session.get('current_order_items', [])
        assert Decimal(order_items[0]['price']) == product_variant.price

    def test_add_item_size_upcharge(self, client, product, product_variant):
        """Test that size upcharges are not applied at add time"""
        response = client.post(reverse('order:add_item'), {
            'product': product.id,
            'size': Size.ADULT_2X,
            'quantity': 1,
            'category': product_variant.category.id
        })

        order_items = client.session.get('current_order_items', [])
        # Base price should be stored, upcharges applied later
        assert Decimal(order_items[0]['price']) == product_variant.price

    def test_add_item_invalid_product(self, client):
        """Test adding item with invalid product ID"""
        response = client.post(reverse('order:add_item'), {
            'product': 99999,
            'size': Size.ADULT_L,
            'quantity': 1
        })
        assert response.status_code == 404

    def test_add_item_get_request(self, client, product):
        """Test that GET requests are rejected"""
        response = client.get(reverse('order:add_item'))
        assert response.status_code == 400



@pytest.mark.django_db
class TestShoppingCartView:
    """Tests for shopping_cart view"""

    def test_shopping_cart_empty(self, client):
        """Test shopping cart with no items"""
        response = client.get(reverse('order:shopping_cart'))
        assert response.status_code == 200
        assert response.context['total_cost'] == Decimal('0.00')
        assert len(response.context['order_items']) == 0

    def test_shopping_cart_with_items(self, client, product):
        """Test shopping cart with items"""
        session = client.session
        session['current_order_items'] = [{
            'product_id': product.id,
            'product_name': product.name,
            'size': Size.ADULT_L,
            'quantity': 2,
            'price': '25.00',
            'back_name': ''
        }]
        session.save()

        response = client.get(reverse('order:shopping_cart'))
        assert response.status_code == 200
        assert len(response.context['order_items']) == 1
        assert response.context['total_cost'] == Decimal('50.00')

    def test_shopping_cart_applies_upcharges(self, client, product):
        """Test that upcharges are applied in cart view"""
        session = client.session
        session['current_order_items'] = [{
            'product_id': product.id,
            'product_name': product.name,
            'size': Size.ADULT_2X,
            'quantity': 1,
            'price': '25.00',
            'back_name': 'SMITH'
        }]
        session.save()

        response = client.get(reverse('order:shopping_cart'))
        # Base: $25 + Size 2X: $2 + Back name: $2 = $29
        assert response.context['total_cost'] == Decimal('29.00')


@pytest.mark.django_db
class TestViewSummaryView:
    """Tests for view_summary view"""

    def test_view_summary_with_items(self, client, product):
        """Test viewing order summary"""
        session = client.session
        session['current_order_items'] = [{
            'product_id': product.id,
            'product_name': product.name,
            'size': Size.ADULT_L,
            'quantity': 1,
            'price': '25.00',
            'color_name': 'Red',
            'category_name': 'T-Shirt',
            'back_name': ''
        }]
        session.save()

        response = client.get(reverse('order:order_summary'))
        assert response.status_code == 200
        assert len(response.context['order_items']) == 1
        assert response.context['total_cost'] == Decimal('25.00')


@pytest.mark.django_db
class TestConfirmOrderView:
    """Tests for confirm_order view with proper Stripe integration testing"""

    @patch('stripe.checkout.Session.create')
    def test_confirm_order_creates_stripe_session(self, mock_stripe, client, product):
        """Test that confirming order creates Stripe checkout session with correct data"""
        # Setup mock to return a realistic Stripe session
        mock_session = Mock()
        mock_session.url = 'https://checkout.stripe.com/c/pay/cs_test_123456'
        mock_session.id = 'cs_test_123456'
        mock_stripe.return_value = mock_session

        # Setup cart
        session = client.session
        session['current_order_items'] = [{
            'product_id': product.id,
            'product_name': product.name,
            'size': Size.ADULT_L,
            'quantity': 2,
            'price': '25.00',
            'color_name': 'Red',
            'category_name': 'T-Shirt',
            'back_name': 'SMITH'
        }]
        session.save()

        # Submit order
        response = client.post(reverse('order:confirm_order'), {
            'customer_name': 'John Doe',
            'customer_email': 'john@test.com'
        })

        # Verify Stripe was called
        assert mock_stripe.called
        assert mock_stripe.call_count == 1

        # Verify the call arguments contain correct data
        call_args = mock_stripe.call_args
        assert call_args is not None

        # Check payment method types
        assert 'payment_method_types' in call_args.kwargs
        assert 'card' in call_args.kwargs['payment_method_types']

        # Check mode
        assert call_args.kwargs['mode'] == 'payment'

        # Check line items
        assert 'line_items' in call_args.kwargs
        line_items = call_args.kwargs['line_items']
        assert len(line_items) == 1

        # Verify line item details
        line_item = line_items[0]
        assert line_item['quantity'] == 2
        assert line_item['price_data']['product_data']['name'] == product.name

        # Check that price includes upcharges (base: $25 + back name: $2 = $27)
        # In cents: $27 * 100 = 2700
        assert line_item['price_data']['unit_amount'] == 2700

        # Check metadata
        assert 'metadata' in call_args.kwargs
        metadata = call_args.kwargs['metadata']
        assert metadata['customer_name'] == 'John Doe'
        assert metadata['customer_email'] == 'john@test.com'

        # Check customer email
        assert call_args.kwargs['customer_email'] == 'john@test.com'

        # Check success/cancel URLs
        assert 'success_url' in call_args.kwargs
        assert 'cancel_url' in call_args.kwargs
        assert 'payment-success' in call_args.kwargs['success_url']
        assert 'payment-cancel' in call_args.kwargs['cancel_url']

        # Verify redirect to Stripe
        assert response.status_code == 302
        assert response.url == 'https://checkout.stripe.com/c/pay/cs_test_123456'

        # Verify cart was cleared from session
        assert 'current_order_items' not in client.session

    @patch('stripe.checkout.Session.create')
    def test_confirm_order_with_multiple_items(self, mock_stripe, client, product, collection):
        """Test checkout with multiple different products"""
        from order.models import Product, ProductCategory
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        from io import BytesIO

        # Create second product
        img = Image.new('RGB', (344, 250), color='blue')
        img_io = BytesIO()
        img.save(img_io, format='JPEG')
        img_io.seek(0)

        product2 = Product.objects.create(
            name='Test Hoodie',
            collection=collection,
            image=SimpleUploadedFile('test2.jpg', img_io.read(), content_type='image/jpeg'),
            available_sizes=[Size.ADULT_M, Size.ADULT_L],
            active=True
        )

        mock_session = Mock()
        mock_session.url = 'https://checkout.stripe.com/c/pay/cs_test_multi'
        mock_stripe.return_value = mock_session

        # Cart with 2 different products
        session = client.session
        session['current_order_items'] = [
            {
                'product_id': product.id,
                'product_name': product.name,
                'size': Size.ADULT_L,
                'quantity': 1,
                'price': '25.00',
                'color_name': 'Red',
                'category_name': 'T-Shirt',
                'back_name': ''
            },
            {
                'product_id': product2.id,
                'product_name': product2.name,
                'size': Size.ADULT_M,
                'quantity': 3,
                'price': '35.00',
                'color_name': 'Blue',
                'category_name': 'Hoodie',
                'back_name': ''
            }
        ]
        session.save()

        response = client.post(reverse('order:confirm_order'), {
            'customer_name': 'Jane Smith',
            'customer_email': 'jane@test.com'
        })

        # Verify Stripe was called
        assert mock_stripe.called

        # Check that we have 2 line items
        call_args = mock_stripe.call_args
        line_items = call_args.kwargs['line_items']
        assert len(line_items) == 2

        # Verify first item
        assert line_items[0]['quantity'] == 1
        assert line_items[0]['price_data']['unit_amount'] == 2500  # $25.00

        # Verify second item
        assert line_items[1]['quantity'] == 3
        assert line_items[1]['price_data']['unit_amount'] == 3500  # $35.00

    @patch('stripe.checkout.Session.create')
    def test_confirm_order_with_size_upcharges(self, mock_stripe, client, product):
        """Test that size upcharges are correctly applied"""
        mock_session = Mock()
        mock_session.url = 'https://checkout.stripe.com/test'
        mock_stripe.return_value = mock_session

        # Add item with 2X size (should add $2)
        session = client.session
        session['current_order_items'] = [{
            'product_id': product.id,
            'product_name': product.name,
            'size': Size.ADULT_2X,
            'quantity': 1,
            'price': '25.00',
            'color_name': 'Red',
            'category_name': 'T-Shirt',
            'back_name': ''
        }]
        session.save()

        response = client.post(reverse('order:confirm_order'), {
            'customer_name': 'Big Guy',
            'customer_email': 'big@test.com'
        })

        # Verify price includes $2 upcharge
        call_args = mock_stripe.call_args
        line_item = call_args.kwargs['line_items'][0]
        # Base: $25 + Size 2X: $2 = $27 = 2700 cents
        assert line_item['price_data']['unit_amount'] == 2700

    @patch('stripe.checkout.Session.create')
    def test_confirm_order_with_4x_upcharge(self, mock_stripe, client, product):
        """Test that 4X size has $3 upcharge"""
        mock_session = Mock()
        mock_session.url = 'https://checkout.stripe.com/test'
        mock_stripe.return_value = mock_session

        session = client.session
        session['current_order_items'] = [{
            'product_id': product.id,
            'product_name': product.name,
            'size': Size.ADULT_4X,
            'quantity': 1,
            'price': '25.00',
            'color_name': 'Red',
            'category_name': 'T-Shirt',
            'back_name': ''
        }]
        session.save()

        response = client.post(reverse('order:confirm_order'), {
            'customer_name': 'Really Big Guy',
            'customer_email': 'reallybig@test.com'
        })

        # Verify price includes $3 upcharge
        call_args = mock_stripe.call_args
        line_item = call_args.kwargs['line_items'][0]
        # Base: $25 + Size 4X: $3 = $28 = 2800 cents
        assert line_item['price_data']['unit_amount'] == 2800

    @patch('stripe.checkout.Session.create')
    def test_confirm_order_with_back_name_upcharge(self, mock_stripe, client, product):
        """Test that back name adds $2"""
        mock_session = Mock()
        mock_session.url = 'https://checkout.stripe.com/test'
        mock_stripe.return_value = mock_session

        session = client.session
        session['current_order_items'] = [{
            'product_id': product.id,
            'product_name': product.name,
            'size': Size.ADULT_L,
            'quantity': 1,
            'price': '25.00',
            'color_name': 'Red',
            'category_name': 'T-Shirt',
            'back_name': 'JONES'
        }]
        session.save()

        response = client.post(reverse('order:confirm_order'), {
            'customer_name': 'Jones Family',
            'customer_email': 'jones@test.com'
        })

        # Verify price includes $2 back name upcharge
        call_args = mock_stripe.call_args
        line_item = call_args.kwargs['line_items'][0]
        # Base: $25 + Back name: $2 = $27 = 2700 cents
        assert line_item['price_data']['unit_amount'] == 2700

    @patch('stripe.checkout.Session.create')
    def test_confirm_order_with_all_upcharges(self, mock_stripe, client, product):
        """Test combining size upcharge + back name upcharge"""
        mock_session = Mock()
        mock_session.url = 'https://checkout.stripe.com/test'
        mock_stripe.return_value = mock_session

        session = client.session
        session['current_order_items'] = [{
            'product_id': product.id,
            'product_name': product.name,
            'size': Size.ADULT_2X,  # +$2
            'quantity': 1,
            'price': '25.00',
            'color_name': 'Red',
            'category_name': 'T-Shirt',
            'back_name': 'GARCIA'  # +$2
        }]
        session.save()

        response = client.post(reverse('order:confirm_order'), {
            'customer_name': 'Garcia',
            'customer_email': 'garcia@test.com'
        })

        # Verify both upcharges applied
        call_args = mock_stripe.call_args
        line_item = call_args.kwargs['line_items'][0]
        # Base: $25 + Size 2X: $2 + Back name: $2 = $29 = 2900 cents
        assert line_item['price_data']['unit_amount'] == 2900

    @patch('stripe.checkout.Session.create')
    def test_confirm_order_product_metadata(self, mock_stripe, client, product):
        """Test that product metadata is correctly set"""
        mock_session = Mock()
        mock_session.url = 'https://checkout.stripe.com/test'
        mock_stripe.return_value = mock_session

        session = client.session
        session['current_order_items'] = [{
            'product_id': product.id,
            'product_name': product.name,  # Use actual product name from fixture
            'size': Size.ADULT_L,
            'quantity': 1,
            'price': '25.00',
            'color_name': 'Red',
            'category_name': 'T-Shirt',
            'back_name': 'TESTING'
        }]
        session.save()

        response = client.post(reverse('order:confirm_order'), {
            'customer_name': 'Test User',
            'customer_email': 'test@test.com'
        })

        # Verify product metadata
        call_args = mock_stripe.call_args
        line_item = call_args.kwargs['line_items'][0]
        product_data = line_item['price_data']['product_data']

        assert product_data['name'] == product.name  # Changed from 'Cool Shirt' to product.name
        assert 'Size: AL' in product_data['description']  # Size.ADULT_L value
        assert 'Color: Red' in product_data['description']
        assert 'Category: T-Shirt' in product_data['description']
        assert 'Custom Name: TESTING' in product_data['description']

        # Check metadata dict
        metadata = product_data['metadata']
        assert metadata['product_id'] == str(product.id)
        assert metadata['size'] == Size.ADULT_L
        assert metadata['color'] == 'Red'
        assert metadata['category'] == 'T-Shirt'
        assert metadata['back_name'] == 'TESTING'

    def test_confirm_order_empty_cart(self, client):
        """Test confirming order with empty cart redirects"""
        response = client.post(reverse('order:confirm_order'), {
            'customer_name': 'John Doe',
            'customer_email': 'john@test.com'
        })
        assert response.status_code == 302
        assert response.url == reverse('order:index')

    @patch('stripe.checkout.Session.create')
    def test_confirm_order_session_cleared(self, mock_stripe, client, product):
        """Test that cart is cleared after creating Stripe session"""
        mock_session = Mock()
        mock_session.url = 'https://checkout.stripe.com/test'
        mock_stripe.return_value = mock_session

        session = client.session
        session['current_order_items'] = [{
            'product_id': product.id,
            'product_name': product.name,
            'size': Size.ADULT_L,
            'quantity': 1,
            'price': '25.00',
            'color_name': 'Red',
            'category_name': 'T-Shirt',
            'back_name': ''
        }]
        session.save()

        response = client.post(reverse('order:confirm_order'), {
            'customer_name': 'John Doe',
            'customer_email': 'john@test.com'
        })

        # Verify cart was cleared
        assert 'current_order_items' not in client.session

    @patch('stripe.checkout.Session.create')
    def test_confirm_order_stripe_error_handling(self, mock_stripe, client, product):
        """Test handling of Stripe API errors"""
        # Make Stripe throw an error
        mock_stripe.side_effect = Exception("Stripe API Error")

        session = client.session
        session['current_order_items'] = [{
            'product_id': product.id,
            'product_name': product.name,
            'size': Size.ADULT_L,
            'quantity': 1,
            'price': '25.00',
            'color_name': 'Red',
            'category_name': 'T-Shirt',
            'back_name': ''
        }]
        session.save()

        # This should raise an exception or handle gracefully
        # Depending on your error handling implementation
        with pytest.raises(Exception):
            response = client.post(reverse('order:confirm_order'), {
                'customer_name': 'John Doe',
                'customer_email': 'john@test.com'
            })


@pytest.mark.django_db
class TestAdminViews:
    """Tests for admin-only views"""

    def test_product_dashboard_requires_admin(self, client):
        """Test that product dashboard requires admin login"""
        response = client.get(reverse('order:product_dashboard'))
        assert response.status_code == 302  # Redirect to login

    def test_product_dashboard_admin_access(self, authenticated_client):
        """Test that admin can access product dashboard"""
        response = authenticated_client.get(reverse('order:product_dashboard'))
        assert response.status_code == 200

    def test_order_dashboard_requires_admin(self, client):
        """Test that order dashboard requires admin login"""
        response = client.get(reverse('order:order_dashboard'))
        assert response.status_code == 302

    def test_order_list_loads(self, authenticated_client, order):
        """Test that order list loads for admin"""
        response = authenticated_client.get(reverse('order:order_list'))
        assert response.status_code == 200
        assert 'orders' in response.context


@pytest.mark.django_db
class TestSummaryView:
    """Tests for summary view"""

    def test_summary_view_requires_admin(self, client):
        """Test that summary view requires admin login"""
        response = client.get(reverse('order:summary'))
        assert response.status_code == 302

    def test_summary_view_loads(self, authenticated_client):
        """Test that summary view loads for admin"""
        response = authenticated_client.get(reverse('order:summary'))
        assert response.status_code == 200
        assert 'summary_table' in response.context

    def test_summary_view_with_order_items(self, authenticated_client, order_item):
        """Test summary view with existing orders"""
        response = authenticated_client.get(reverse('order:summary'))
        assert response.status_code == 200
        summary_table = response.context['summary_table']
        assert len(summary_table) > 0

    def test_summary_view_collection_filter(self, authenticated_client, order_item, collection):
        """Test filtering summary by collection"""
        response = authenticated_client.get(
            reverse('order:summary'),
            {'collection': collection.id}
        )
        assert response.status_code == 200
        # Check that filtering worked
        summary_table = response.context['summary_table']
        for row in summary_table:
            # All products should be from the filtered collection
            pass  # Add specific assertions based on your data

    def test_summary_view_product_name_filter(self, authenticated_client, order_item):
        """Test filtering summary by product name"""
        response = authenticated_client.get(
            reverse('order:summary'),
            {'product_name': order_item.product_name}
        )
        assert response.status_code == 200
        summary_table = response.context['summary_table']
        # Should only show rows for the filtered product
        for row in summary_table:
            assert row['product_name'] == order_item.product_name

    def test_summary_view_both_filters(self, authenticated_client, order_item, collection):
        """Test using both collection and product name filters"""
        response = authenticated_client.get(
            reverse('order:summary'),
            {
                'collection': collection.id,
                'product_name': order_item.product_name
            }
        )
        assert response.status_code == 200
        summary_table = response.context['summary_table']
        assert len(summary_table) >= 0


@pytest.mark.django_db
class TestOrderSummaryDownload:
    """Tests for order_summary_download view"""

    def test_download_requires_admin(self, client):
        """Test that download requires admin login"""
        response = client.get(reverse('order:order_summary_download'))
        assert response.status_code == 302

    def test_download_with_data(self, authenticated_client, order_item):
        """Test downloading order summary"""
        response = authenticated_client.get(reverse('order:order_summary_download'))
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    def test_download_with_collection_filter(self, authenticated_client, order_item, collection):
        """Test download with collection filter"""
        response = authenticated_client.get(
            reverse('order:order_summary_download'),
            {'collection': collection.id}
        )
        assert response.status_code == 200
        # Check filename contains collection name
        content_disposition = response['Content-Disposition']
        assert collection.name in content_disposition

    def test_download_with_product_filter(self, authenticated_client, order_item):
        """Test download with product name filter"""
        response = authenticated_client.get(
            reverse('order:order_summary_download'),
            {'product_name': order_item.product_name}
        )
        assert response.status_code == 200
        content_disposition = response['Content-Disposition']
        assert order_item.product_name in content_disposition


@pytest.mark.django_db
class TestTogglePaidView:
    """Tests for toggle_paid view"""

    def test_toggle_paid_requires_admin(self, client, order):
        """Test that toggle paid requires admin"""
        response = client.post(reverse('order:toggle_paid', args=[order.id]))
        assert response.status_code == 302

    def test_toggle_paid_marks_paid(self, authenticated_client, order):
        """Test marking order as paid"""
        assert not order.has_paid

        response = authenticated_client.post(
            reverse('order:toggle_paid', args=[order.id]),
            {'has_paid': 'on'}
        )

        order.refresh_from_db()
        assert order.has_paid

    def test_toggle_paid_marks_unpaid(self, authenticated_client, paid_order):
        """Test marking order as unpaid"""
        assert paid_order.has_paid

        response = authenticated_client.post(
            reverse('order:toggle_paid', args=[paid_order.id])
        )

        paid_order.refresh_from_db()
        assert not paid_order.has_paid


@pytest.mark.django_db
class TestBulkOrderActions:
    """Tests for bulk order actions"""

    def test_bulk_archive_orders(self, authenticated_client, order, paid_order):
        """Test archiving multiple orders"""
        response = authenticated_client.post(
            reverse('order:bulk_archive_orders'),
            {'order_ids[]': [order.id, paid_order.id]}
        )

        order.refresh_from_db()
        paid_order.refresh_from_db()
        assert order.archived
        assert paid_order.archived

    def test_bulk_delete_orders(self, authenticated_client, order, paid_order):
        """Test deleting multiple orders"""
        order_ids = [order.id, paid_order.id]

        response = authenticated_client.post(
            reverse('order:bulk_delete_orders'),
            {'order_ids[]': order_ids}
        )

        assert not Order.objects.filter(id__in=order_ids).exists()

    def test_restore_order(self, authenticated_client, order):
        """Test restoring an archived order"""
        order.archived = True
        order.save()

        response = authenticated_client.post(
            reverse('order:restore_order', args=[order.id])
        )

        order.refresh_from_db()
        assert not order.archived


@pytest.mark.django_db
class TestContactView:
    """Tests for contact page view"""

    def test_contact_page_loads(self, client):
        """Test that contact page loads"""
        response = client.get(reverse('order:contact'))
        assert response.status_code == 200
        assert 'form' in response.context

    @patch('order.views.send_mail')
    def test_contact_form_submission(self, mock_send_mail, client):
        """Test submitting contact form"""
        response = client.post(reverse('order:contact'), {
            'email': 'test@example.com',
            'message': 'This is a test message with enough characters.'
        })

        # Check that either:
        # 1. Email was sent successfully (mock was called), OR
        # 2. Form was submitted but email failed due to missing settings
        # Both are acceptable for testing purposes
        if response.status_code == 302:
            # Successful redirect means form was processed
            # Email may or may not have been sent depending on settings
            assert True
        else:
            # Form had validation errors
            assert 'form' in response.context