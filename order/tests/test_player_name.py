"""
Tests for the collection-level player name feature.

A collection can opt in with ``has_player_name``.  When the cart holds an item
from such a collection, the checkout form in the cart asks for a player name
once, and that name is applied to every qualifying item on the order.
"""
import re

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.urls import reverse

from order.forms import CollectionForm
from order.models import Collection, Order, OrderItem, Size
from order.stripe_orders import create_order_from_checkout_session
from order.views import orders_have_player_names


@pytest.fixture
def authenticated_client(client, admin_user):
    """Provides an admin-authenticated client"""
    client.force_login(admin_user)
    return client


@pytest.fixture(autouse=True)
def clear_cache_for_tests():
    """Clear cache before and after each test to reset rate limits"""
    cache.clear()
    yield
    cache.clear()


def cart_item(product, size=Size.ADULT_L, price='40.00'):
    """Builds a session cart entry the way add_item does"""
    return {
        'product_id': product.id,
        'product_name': product.name,
        'size': size,
        'quantity': 1,
        'color_name': 'Red',
        'category_name': 'T-Shirt',
        'price': price,
        'back_name': '',
    }


def set_cart(client, items):
    session = client.session
    session['current_order_items'] = items
    session.save()


def stripe_line_items(mock_stripe):
    return mock_stripe.call_args.kwargs['line_items']


def stripe_product_data(mock_stripe, index=0):
    return stripe_line_items(mock_stripe)[index]['price_data']['product_data']


@pytest.mark.django_db
class TestCollectionPlayerNameField:
    """The toggle on the collection itself"""

    def test_collection_defaults_to_no_player_name(self, collection):
        """Existing collections keep working without opting in"""
        assert collection.has_player_name is False

    def test_player_name_collection_fixture_opts_in(self, player_name_collection):
        assert player_name_collection.has_player_name is True

    def test_collection_form_exposes_player_name_toggle(self):
        """The collection modal renders the new toggle"""
        form = CollectionForm()
        assert 'has_player_name' in form.fields

    def test_collection_form_saves_player_name_toggle(self):
        form = CollectionForm(data={
            'name': 'Fall Roster',
            'has_player_name': True,
            'active': True,
        })
        assert form.is_valid(), form.errors
        collection = form.save()
        assert collection.has_player_name is True

    def test_collection_form_valid_without_player_name(self):
        """Omitting the checkbox leaves the collection opted out"""
        form = CollectionForm(data={'name': 'Plain Collection', 'active': True})
        assert form.is_valid(), form.errors
        assert form.save().has_player_name is False

    def test_collection_create_view_saves_toggle(self, authenticated_client):
        response = authenticated_client.post(reverse('order:collection_create'), {
            'name': 'Created Roster',
            'has_player_name': 'on',
            'active': 'on',
        })

        assert response.status_code == 204
        assert Collection.objects.get(name='Created Roster').has_player_name is True

    def test_collection_update_view_toggles_player_name(self, authenticated_client, collection):
        response = authenticated_client.post(
            reverse('order:collection_update', args=[collection.id]),
            {'name': collection.name, 'has_player_name': 'on', 'active': 'on'},
        )

        assert response.status_code == 204
        collection.refresh_from_db()
        assert collection.has_player_name is True

    def test_collection_update_view_can_turn_player_name_off(
        self, authenticated_client, player_name_collection
    ):
        response = authenticated_client.post(
            reverse('order:collection_update', args=[player_name_collection.id]),
            {'name': player_name_collection.name, 'active': 'on'},
        )

        assert response.status_code == 204
        player_name_collection.refresh_from_db()
        assert player_name_collection.has_player_name is False

    def test_create_modal_renders_player_name_toggle(self, authenticated_client):
        """The create-collection modal shows the checkbox"""
        response = authenticated_client.get(reverse('order:collection_create'))
        content = response.content.decode()

        assert response.status_code == 200
        assert 'has_player_name' in content
        assert 'Require a player name' in content

    def test_update_modal_renders_player_name_toggle(
        self, authenticated_client, player_name_collection
    ):
        """The update-collection modal shows the checkbox pre-checked"""
        response = authenticated_client.get(
            reverse('order:collection_update', args=[player_name_collection.id])
        )
        content = response.content.decode()

        assert response.status_code == 200
        # The checkbox itself must carry `checked`, not merely some other field.
        field_tag = re.search(r'<input[^>]*has_player_name[^>]*>', content)
        assert field_tag is not None
        assert 'checked' in field_tag.group()

    def test_collections_list_marks_player_name_collections(
        self, authenticated_client, player_name_collection, collection
    ):
        response = authenticated_client.get(reverse('order:collection_list'))
        content = response.content.decode()

        assert response.status_code == 200
        assert 'Player Name' in content
        assert 'Required' in content


@pytest.mark.django_db
class TestPlayerNameFieldLivesInTheCart:
    """The customer types the name once, in the cart — not on every product"""

    def test_product_card_does_not_ask_for_player_name(self, client, player_name_product):
        """Each product tile stays free of the field"""
        session = client.session
        session['selected_collection_id'] = player_name_product.collection.id
        session.save()

        response = client.get(reverse('order:index'))
        products_markup = response.content.decode().split('id="cart-sidebar"')[0]

        assert 'name="player_name"' not in products_markup

    def test_cart_checkout_form_holds_the_single_input(self, client):
        """The cart's checkout form owns the one player name input"""
        response = client.get(reverse('order:index'))
        content = response.content.decode()

        assert 'id="checkout-player-name"' in content
        assert 'name="player_name"' in content

    def test_cart_input_starts_disabled(self, client):
        """Disabled until the cart needs it, so it is never submitted by accident"""
        response = client.get(reverse('order:index'))
        content = response.content.decode()

        field_tag = re.search(r'<input[^>]*id="checkout-player-name"[^>]*>', content)
        assert field_tag is not None
        assert 'disabled' in field_tag.group()

    def test_cart_input_is_inside_the_checkout_form(self, client):
        """An input outside the form would never reach confirm_order"""
        content = client.get(reverse('order:index')).content.decode()

        form_markup = content.split('id="checkout-form"')[1].split('</form>')[0]
        assert 'id="checkout-player-name"' in form_markup

    def test_toggle_function_is_defined_in_the_page(self, client):
        """The cart partial calls this; a stale static bundle must not break it.

        WhiteNoise serves the collected copy of static/js even in DEBUG, so the
        toggle lives inline in base.html where it cannot go out of date.
        """
        content = client.get(reverse('order:index')).content.decode()

        assert 'function togglePlayerNameField' in content

    def test_toggle_is_defined_before_the_cart_calls_it(self, client, player_name_product):
        """Definition must precede the HTMX-loaded cart partial's call"""
        page = client.get(reverse('order:index')).content.decode()
        assert 'function togglePlayerNameField' in page

        set_cart(client, [cart_item(player_name_product)])
        partial = client.get(reverse('order:shopping_cart')).content.decode()
        assert 'togglePlayerNameField(' in partial
        # The partial never defines it; it relies on the page-level definition.
        assert 'function togglePlayerNameField' not in partial


@pytest.mark.django_db
class TestCartRequestsPlayerNameWhenNeeded:
    """shopping_cart tells the checkout form whether to ask"""

    def test_cart_requests_name_for_flagged_collection(self, client, player_name_product):
        set_cart(client, [cart_item(player_name_product)])

        response = client.get(reverse('order:shopping_cart'))

        assert response.status_code == 200
        assert response.context['requires_player_name'] is True
        # The partial must tell the checkout form to reveal the field.
        assert re.search(
            r'togglePlayerNameField\(\s*true\s*\)', response.content.decode()
        )

    def test_cart_does_not_request_name_for_regular_collection(self, client, product):
        set_cart(client, [cart_item(product, price='25.00')])

        response = client.get(reverse('order:shopping_cart'))

        assert response.status_code == 200
        assert response.context['requires_player_name'] is False
        assert re.search(
            r'togglePlayerNameField\(\s*false\s*\)', response.content.decode()
        )

    def test_mixed_cart_requests_name(self, client, product, player_name_product):
        """One qualifying item is enough to ask"""
        set_cart(client, [
            cart_item(product, price='25.00'),
            cart_item(player_name_product),
        ])

        response = client.get(reverse('order:shopping_cart'))

        assert response.context['requires_player_name'] is True

    def test_empty_cart_does_not_request_name(self, client):
        response = client.get(reverse('order:shopping_cart'))

        assert response.status_code == 200
        assert response.context['requires_player_name'] is False

    def test_summary_modal_asks_for_name_when_needed(self, client, player_name_product):
        set_cart(client, [cart_item(player_name_product)])

        response = client.get(reverse('order:order_summary'))
        content = response.content.decode()

        assert response.context['requires_player_name'] is True
        assert 'name="player_name"' in content

    def test_summary_modal_omits_name_when_not_needed(self, client, product):
        set_cart(client, [cart_item(product, price='25.00')])

        response = client.get(reverse('order:order_summary'))

        assert response.context['requires_player_name'] is False
        assert 'name="player_name"' not in response.content.decode()


@pytest.mark.django_db
class TestAddItemIsUnaffected:
    """Adding to the cart no longer touches player names"""

    def test_add_item_does_not_store_a_player_name(
        self, client, player_name_product, product_category
    ):
        response = client.post(reverse('order:add_item'), {
            'product': player_name_product.id,
            'size': Size.ADULT_L,
            'quantity': 1,
            'category': product_category.id,
        })

        assert response.status_code == 204
        assert 'player_name' not in client.session['current_order_items'][0]

    def test_add_item_succeeds_without_a_name_for_flagged_collection(
        self, client, player_name_product, product_category
    ):
        """The name is collected at checkout, so adding must not be blocked"""
        response = client.post(reverse('order:add_item'), {
            'product': player_name_product.id,
            'size': Size.ADULT_L,
            'quantity': 1,
            'category': product_category.id,
        })

        assert response.status_code == 204
        assert len(client.session['current_order_items']) == 1

    def test_add_item_ignores_a_posted_player_name(
        self, client, player_name_product, product_category
    ):
        client.post(reverse('order:add_item'), {
            'product': player_name_product.id,
            'size': Size.ADULT_L,
            'quantity': 1,
            'category': product_category.id,
            'player_name': 'Ignored At This Stage',
        })

        item = client.session['current_order_items'][0]
        assert 'Ignored At This Stage' not in str(item)

    def test_add_item_still_handles_back_name(self, client, product, product_category):
        """Existing behaviour is untouched"""
        response = client.post(reverse('order:add_item'), {
            'product': product.id,
            'size': Size.ADULT_L,
            'quantity': 1,
            'category': product_category.id,
            'back_name': 'SMITH',
        })

        assert response.status_code == 204
        assert client.session['current_order_items'][0]['back_name'] == 'SMITH'


@pytest.mark.django_db
class TestPlayerNameAtCheckout:
    """confirm_order spreads the single name across qualifying items"""

    @pytest.fixture
    def mock_stripe(self):
        with patch('stripe.checkout.Session.create') as mock:
            session = Mock()
            session.url = 'https://checkout.stripe.com/test'
            mock.return_value = session
            yield mock

    def _checkout(self, client, **extra):
        payload = {'customer_name': 'Test User', 'customer_email': 'test@test.com'}
        payload.update(extra)
        return client.post(reverse('order:confirm_order'), payload)

    def test_one_name_applies_to_every_item(
        self, mock_stripe, client, player_name_product
    ):
        """Typed once in the cart, attached to all items from that collection"""
        set_cart(client, [
            cart_item(player_name_product, size=Size.ADULT_L),
            cart_item(player_name_product, size=Size.ADULT_M),
        ])

        self._checkout(client, player_name='Jordan Reyes')

        assert len(stripe_line_items(mock_stripe)) == 2
        for index in range(2):
            data = stripe_product_data(mock_stripe, index)
            assert data['metadata']['player_name'] == 'Jordan Reyes'
            assert 'Player: Jordan Reyes' in data['description']

    def test_name_only_attaches_to_flagged_collection_items(
        self, mock_stripe, client, product, player_name_product
    ):
        """A mixed cart leaves ordinary items alone"""
        set_cart(client, [
            cart_item(product, price='25.00'),
            cart_item(player_name_product),
        ])

        self._checkout(client, player_name='Jordan Reyes')

        by_name = {
            stripe_product_data(mock_stripe, i)['name']: stripe_product_data(mock_stripe, i)
            for i in range(len(stripe_line_items(mock_stripe)))
        }
        assert by_name[product.name]['metadata']['player_name'] == ''
        assert by_name[player_name_product.name]['metadata']['player_name'] == 'Jordan Reyes'

    def test_checkout_is_blocked_without_a_required_name(
        self, mock_stripe, client, player_name_product
    ):
        """Server-side backstop for the required input"""
        set_cart(client, [cart_item(player_name_product)])

        response = self._checkout(client)

        assert response.status_code == 302
        assert response.url == reverse('order:index')
        mock_stripe.assert_not_called()

    def test_blocked_checkout_preserves_the_cart(
        self, mock_stripe, client, player_name_product
    ):
        """The customer should only have to add the name they missed"""
        set_cart(client, [cart_item(player_name_product)])

        self._checkout(client)

        assert len(client.session['current_order_items']) == 1

    def test_blank_name_is_treated_as_missing(
        self, mock_stripe, client, player_name_product
    ):
        set_cart(client, [cart_item(player_name_product)])

        response = self._checkout(client, player_name='   ')

        assert response.status_code == 302
        mock_stripe.assert_not_called()

    def test_name_is_stripped(self, mock_stripe, client, player_name_product):
        set_cart(client, [cart_item(player_name_product)])

        self._checkout(client, player_name='  Jordan Reyes  ')

        assert stripe_product_data(mock_stripe)['metadata']['player_name'] == 'Jordan Reyes'

    def test_name_is_capped_at_model_length(
        self, mock_stripe, client, player_name_product
    ):
        """An oversized name must not fail the order write that happens after payment"""
        set_cart(client, [cart_item(player_name_product)])

        self._checkout(client, player_name='A' * 500)

        stored = stripe_product_data(mock_stripe)['metadata']['player_name']
        assert len(stored) == OrderItem._meta.get_field('player_name').max_length

    def test_posted_name_is_discarded_for_regular_collections(
        self, mock_stripe, client, product
    ):
        """A crafted post cannot attach a name where none is collected"""
        set_cart(client, [cart_item(product, price='25.00')])

        self._checkout(client, player_name='Should Be Ignored')

        data = stripe_product_data(mock_stripe)
        assert data['metadata']['player_name'] == ''
        assert 'Player:' not in data['description']

    def test_checkout_without_names_keeps_original_payload(
        self, mock_stripe, client, product
    ):
        set_cart(client, [cart_item(product, price='25.00')])

        response = self._checkout(client)

        assert response.status_code == 302
        data = stripe_product_data(mock_stripe)
        assert data['metadata']['player_name'] == ''
        assert 'Player:' not in data['description']

    def test_legacy_cart_entries_still_check_out(self, mock_stripe, client, product):
        """A cart stored in a session before this feature shipped still works"""
        legacy = cart_item(product, price='25.00')
        legacy.pop('back_name')
        set_cart(client, [legacy])

        response = self._checkout(client)

        assert response.status_code == 302
        assert stripe_product_data(mock_stripe)['metadata']['player_name'] == ''


@pytest.mark.django_db
class TestPlayerNameRecordedFromStripe:
    """Stripe hands the name back when the payment completes"""

    @patch('order.stripe_orders.stripe.checkout.Session.list_line_items')
    @patch('order.stripe_orders.stripe.checkout.Session.retrieve')
    def test_paid_session_records_player_name(
        self, mock_retrieve, mock_line_items, player_name_product
    ):
        mock_retrieve.return_value = {
            'payment_status': 'paid',
            'metadata': {
                'customer_name': 'Jane Customer',
                'customer_email': 'jane@example.com',
            },
        }
        mock_line_items.return_value = {
            'data': [{
                'description': player_name_product.name,
                'amount_total': 4000,
                'quantity': 1,
                'price': {'product': {
                    'name': player_name_product.name,
                    'metadata': {
                        'product_id': str(player_name_product.id),
                        'size': Size.ADULT_L,
                        'color': 'Red',
                        'category': 'T-Shirt',
                        'back_name': '',
                        'player_name': 'Jordan Reyes',
                    },
                }},
            }],
        }

        order, created = create_order_from_checkout_session('cs_player_name')

        assert created is True
        assert order.items.get().player_name == 'Jordan Reyes'

    @patch('order.stripe_orders.stripe.checkout.Session.list_line_items')
    @patch('order.stripe_orders.stripe.checkout.Session.retrieve')
    def test_paid_session_without_player_name_metadata(
        self, mock_retrieve, mock_line_items, product
    ):
        """Sessions created before this feature shipped still record cleanly"""
        mock_retrieve.return_value = {'payment_status': 'paid', 'metadata': {}}
        mock_line_items.return_value = {
            'data': [{
                'description': product.name,
                'amount_total': 2500,
                'quantity': 1,
                'price': {'product': {
                    'name': product.name,
                    'metadata': {'product_id': str(product.id), 'size': Size.ADULT_L},
                }},
            }],
        }

        order, _ = create_order_from_checkout_session('cs_no_player_name')

        assert order.items.get().player_name == ''


@pytest.mark.django_db
class TestOrderPlayerNamesProperty:
    """Order.player_names drives the dashboard column"""

    def test_collects_distinct_names_in_order(self, order, product):
        for name in ['Jordan Reyes', 'Alex Kim', 'Jordan Reyes']:
            OrderItem.objects.create(
                order=order, product=product, size=Size.ADULT_L,
                quantity=1, product_cost=Decimal('40.00'), player_name=name,
            )

        assert order.player_names == ['Jordan Reyes', 'Alex Kim']

    def test_empty_when_no_item_has_a_name(self, order, order_item):
        assert order.player_names == []

    def test_ignores_blank_and_whitespace_names(self, order, product):
        OrderItem.objects.create(
            order=order, product=product, size=Size.ADULT_L,
            quantity=1, product_cost=Decimal('40.00'), player_name='   ',
        )
        OrderItem.objects.create(
            order=order, product=product, size=Size.ADULT_M,
            quantity=1, product_cost=Decimal('40.00'), player_name=None,
        )

        assert order.player_names == []


@pytest.mark.django_db
class TestPlayerNameColumnOnOrderTable:
    """The dashboard column and its toggle"""

    def _order_with_player_name(self, product, name='Jordan Reyes', archived=False):
        order = Order.objects.create(
            customer_name='Taylor Buyer',
            customer_email='taylor@test.com',
            archived=archived,
        )
        OrderItem.objects.create(
            order=order, product=product, size=Size.ADULT_L,
            quantity=1, product_cost=Decimal('40.00'), player_name=name,
        )
        return order

    def test_orders_have_player_names_detects_names(self, player_name_product):
        assert orders_have_player_names() is False
        self._order_with_player_name(player_name_product)
        assert orders_have_player_names() is True

    def test_orders_have_player_names_ignores_blank(self, product, order):
        OrderItem.objects.create(
            order=order, product=product, size=Size.ADULT_L,
            quantity=1, product_cost=Decimal('25.00'), player_name='',
        )
        assert orders_have_player_names() is False

    def test_orders_have_player_names_separates_archived(self, player_name_product):
        self._order_with_player_name(player_name_product, archived=True)

        assert orders_have_player_names() is False
        assert orders_have_player_names(archived=True) is True

    def test_dashboard_shows_toggle_when_names_exist(
        self, authenticated_client, player_name_product
    ):
        self._order_with_player_name(player_name_product)

        response = authenticated_client.get(reverse('order:order_dashboard'))
        content = response.content.decode()

        assert response.status_code == 200
        assert re.search(r'<input[^>]*id="playerNameToggle"', content)
        assert 'Player Names' in content

    def test_dashboard_hides_toggle_without_names(self, authenticated_client, order_item):
        """No player names anywhere means no extra toggle cluttering the dashboard"""
        response = authenticated_client.get(reverse('order:order_dashboard'))
        content = response.content.decode()

        assert response.status_code == 200
        # The checkbox itself must be absent; the CSS rule naming it is harmless.
        assert not re.search(r'<input[^>]*id="playerNameToggle"', content)
        assert re.search(r'<input[^>]*id="editModeToggle"', content)

    def test_order_list_renders_player_name_in_its_own_column(
        self, authenticated_client, player_name_product
    ):
        """The name lives in a cell tagged for the toggle, not loose in the row"""
        self._order_with_player_name(player_name_product)

        response = authenticated_client.get(reverse('order:order_list'))
        content = response.content.decode()

        assert response.status_code == 200
        assert re.search(r'<th[^>]*player-name-column', content)

        cell = re.search(
            r'<td[^>]*player-name-column[^>]*>(.*?)</td>', content, re.DOTALL
        )
        assert cell is not None
        assert 'Jordan Reyes' in cell.group(1)

    def test_header_and_cells_share_the_toggle_class(
        self, authenticated_client, player_name_product
    ):
        """Both must carry the class the CSS rule targets, or the column half-shows"""
        self._order_with_player_name(player_name_product)

        response = authenticated_client.get(reverse('order:order_list'))
        content = response.content.decode()

        tags = re.findall(r'<t[hd][^>]*player-name-column[^>]*>', content)
        assert len(tags) == 2  # one header, one row cell

    def test_dashboard_css_hides_the_column_until_toggled(
        self, authenticated_client, player_name_product
    ):
        """Visibility is pure CSS — no JS bundle to go stale, no re-sync on swap"""
        self._order_with_player_name(player_name_product)

        content = authenticated_client.get(reverse('order:order_dashboard')).content.decode()

        # Hidden by default...
        assert re.search(r'\.player-name-column\s*\{\s*display:\s*none', content)
        # ...and revealed by the checkbox, with no JavaScript involved.
        assert re.search(
            r'#playerNameToggle:checked\s*\)\s*\.player-name-column\s*\{\s*display:\s*table-cell',
            content,
        )

    def test_column_visibility_needs_no_javascript(self, authenticated_client, player_name_product):
        """The toggle must not depend on static/js, which is served from a collected copy"""
        self._order_with_player_name(player_name_product)

        dashboard = authenticated_client.get(reverse('order:order_dashboard')).content.decode()
        rows = authenticated_client.get(reverse('order:order_list')).content.decode()

        assert re.search(r'<input[^>]*id="playerNameToggle"', dashboard)
        for content in (dashboard, rows):
            assert 'updatePlayerNameColumns' not in content

    def test_order_list_shows_placeholder_for_orders_without_names(
        self, authenticated_client, order_item
    ):
        """Existing orders render a placeholder cell rather than breaking the row"""
        response = authenticated_client.get(reverse('order:order_list'))
        content = response.content.decode()

        assert response.status_code == 200
        assert order_item.order.customer_name in content

        cell = re.search(
            r'<td[^>]*player-name-column[^>]*>(.*?)</td>', content, re.DOTALL
        )
        assert cell is not None
        assert '—' in cell.group(1)

    def test_archived_orders_show_player_name_column(
        self, authenticated_client, player_name_product
    ):
        self._order_with_player_name(player_name_product, archived=True)

        response = authenticated_client.get(reverse('order:archived_orders'))
        content = response.content.decode()

        assert response.status_code == 200
        assert re.search(r'<th[^>]*>\s*Player Name\s*</th>', content)
        assert 'Jordan Reyes' in content

    def test_archived_orders_hide_column_without_names(self, authenticated_client, order):
        order.archived = True
        order.save()

        response = authenticated_client.get(reverse('order:archived_orders'))
        content = response.content.decode()

        assert response.status_code == 200
        # Scoped to the table header: the cart's own field lives on every page.
        assert not re.search(r'<th[^>]*>\s*Player Name\s*</th>', content)

    def test_order_download_succeeds_with_player_names(
        self, authenticated_client, player_name_product
    ):
        self._order_with_player_name(player_name_product)

        response = authenticated_client.get(reverse('order:order_download'))

        assert response.status_code == 200
        assert len(response.content) > 0

    def test_order_download_succeeds_without_player_names(
        self, authenticated_client, order_item
    ):
        response = authenticated_client.get(reverse('order:order_download'))

        assert response.status_code == 200
        assert len(response.content) > 0
