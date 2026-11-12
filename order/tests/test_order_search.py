"""
Tests for order-table pagination and search.

The pairing is the fragile part: page 2 of a search must stay inside the search
results, or the list silently mixes matches with everything else.
"""
import re
from decimal import Decimal

import pytest
from django.urls import reverse

from order.models import Order, OrderItem, Size
from order.views import ORDERS_PER_PAGE


@pytest.fixture
def authenticated_client(client, admin_user):
    client.force_login(admin_user)
    return client


def make_order(name="Buyer", email="buyer@test.com", archived=False, **item_kwargs):
    order = Order.objects.create(
        customer_name=name, customer_email=email, archived=archived
    )
    if item_kwargs:
        OrderItem.objects.create(
            order=order,
            size=item_kwargs.pop("size", Size.ADULT_L),
            quantity=1,
            product_cost=Decimal("25.00"),
            **item_kwargs,
        )
    return order


def row_count(html):
    """Order rows carry the fade-in class; the spinner and empty row do not."""
    return len(re.findall(r'<tr class="[^"]*fade-in"', html))


@pytest.mark.django_db
class TestArchivedPagination:

    def test_archived_list_is_paginated(self, authenticated_client):
        for i in range(ORDERS_PER_PAGE + 5):
            make_order(name=f"Archived {i}", archived=True)

        html = authenticated_client.get(reverse("order:archived_order_list")).content.decode()

        assert row_count(html) == ORDERS_PER_PAGE
        assert "loading-spinner-row" in html

    def test_archived_second_page_returns_the_remainder(self, authenticated_client):
        for i in range(ORDERS_PER_PAGE + 5):
            make_order(name=f"Archived {i}", archived=True)

        response = authenticated_client.get(
            reverse("order:archived_order_list"), {"page": 2}, HTTP_HX_REQUEST="true"
        )
        html = response.content.decode()

        assert row_count(html) == 5
        # Rows only on later pages, so they append into the existing table.
        assert "<table" not in html

    def test_archived_last_page_has_no_spinner(self, authenticated_client):
        for i in range(ORDERS_PER_PAGE + 5):
            make_order(name=f"Archived {i}", archived=True)

        html = authenticated_client.get(
            reverse("order:archived_order_list"), {"page": 2}, HTTP_HX_REQUEST="true"
        ).content.decode()

        assert "loading-spinner-row" not in html

    def test_archive_page_shell_loads(self, authenticated_client):
        make_order(archived=True)
        response = authenticated_client.get(reverse("order:archived_orders"))

        assert response.status_code == 200
        assert 'id="orders-panel"' in response.content.decode()

    def test_active_and_archived_lists_do_not_bleed(self, authenticated_client):
        make_order(name="Active Annie", archived=False)
        make_order(name="Archived Arnie", archived=True)

        active = authenticated_client.get(reverse("order:order_list")).content.decode()
        archived = authenticated_client.get(reverse("order:archived_order_list")).content.decode()

        assert "Active Annie" in active and "Archived Arnie" not in active
        assert "Archived Arnie" in archived and "Active Annie" not in archived


@pytest.mark.django_db
class TestOrderSearch:

    def test_matches_customer_name(self, authenticated_client):
        make_order(name="Jordan Reyes")
        make_order(name="Somebody Else")

        html = authenticated_client.get(
            reverse("order:order_list"), {"q": "jordan"}
        ).content.decode()

        assert "Jordan Reyes" in html
        assert "Somebody Else" not in html

    def test_matches_email(self, authenticated_client):
        make_order(name="A", email="findme@example.com")
        make_order(name="B", email="other@example.com")

        html = authenticated_client.get(
            reverse("order:order_list"), {"q": "findme"}
        ).content.decode()

        assert "findme@example.com" in html
        assert "other@example.com" not in html

    @pytest.mark.parametrize("field,value,term", [
        ("product_name", "Practice Jersey", "jersey"),
        ("product_color", "Crimson", "crimson"),
        ("product_category", "Hoodie", "hoodie"),
        ("back_name", "SMITH", "smith"),
        ("player_name", "Jordan Reyes", "reyes"),
        ("collection_name", "Varsity Roster", "varsity"),
    ])
    def test_matches_anything_on_the_items(self, authenticated_client, field, value, term):
        make_order(name="Match Me", **{field: value})
        make_order(name="Other Person", product_name="Unrelated")

        html = authenticated_client.get(
            reverse("order:order_list"), {"q": term}
        ).content.decode()

        assert "Match Me" in html
        assert "Other Person" not in html

    def test_search_is_case_insensitive(self, authenticated_client):
        make_order(name="Jordan Reyes")

        html = authenticated_client.get(
            reverse("order:order_list"), {"q": "JORDAN"}
        ).content.decode()

        assert "Jordan Reyes" in html

    def test_order_appears_once_when_several_items_match(self, authenticated_client):
        """Joining items would otherwise duplicate the order per matching row"""
        order = make_order(name="Jordan Reyes", product_name="Jersey")
        for _ in range(3):
            OrderItem.objects.create(
                order=order, product_name="Jersey", size=Size.ADULT_M,
                quantity=1, product_cost=Decimal("25.00"),
            )

        html = authenticated_client.get(
            reverse("order:order_list"), {"q": "jersey"}
        ).content.decode()

        assert row_count(html) == 1

    def test_blank_search_returns_everything(self, authenticated_client):
        make_order(name="A")
        make_order(name="B")

        html = authenticated_client.get(
            reverse("order:order_list"), {"q": "   "}
        ).content.decode()

        assert row_count(html) == 2

    def test_no_matches_shows_the_query_back(self, authenticated_client):
        make_order(name="Jordan")

        html = authenticated_client.get(
            reverse("order:order_list"), {"q": "zzzznope"}
        ).content.decode()

        assert row_count(html) == 0
        assert "zzzznope" in html

    def test_search_works_on_archived_too(self, authenticated_client):
        make_order(name="Archived Jordan", archived=True)
        make_order(name="Archived Other", archived=True)

        html = authenticated_client.get(
            reverse("order:archived_order_list"), {"q": "jordan"}
        ).content.decode()

        assert "Archived Jordan" in html
        assert "Archived Other" not in html


@pytest.mark.django_db
class TestSearchAndPaginationTogether:
    """The part most likely to break: paging within a filtered result set."""

    def _make_matching_and_noise(self):
        for i in range(ORDERS_PER_PAGE + 5):
            make_order(name=f"Jordan Reyes {i}")
        for i in range(10):
            make_order(name=f"Unrelated Person {i}")

    def test_first_page_of_a_search_is_capped_and_offers_more(self, authenticated_client):
        self._make_matching_and_noise()

        html = authenticated_client.get(
            reverse("order:order_list"), {"q": "jordan"}
        ).content.decode()

        assert row_count(html) == ORDERS_PER_PAGE
        assert "loading-spinner-row" in html

    def test_spinner_carries_the_search_term_to_the_next_page(self, authenticated_client):
        """Without this the second page would come back unfiltered"""
        self._make_matching_and_noise()

        html = authenticated_client.get(
            reverse("order:order_list"), {"q": "jordan"}
        ).content.decode()

        spinner = re.search(r'id="loading-spinner-row"\s+hx-get="([^"]+)"', html)
        assert spinner is not None
        url = spinner.group(1)
        assert "page=2" in url
        assert "q=jordan" in url

    def test_second_page_of_a_search_stays_within_the_results(self, authenticated_client):
        self._make_matching_and_noise()

        html = authenticated_client.get(
            reverse("order:order_list"),
            {"q": "jordan", "page": 2},
            HTTP_HX_REQUEST="true",
        ).content.decode()

        assert row_count(html) == 5
        assert "Unrelated Person" not in html

    def test_archived_search_pagination_points_at_the_archived_url(self, authenticated_client):
        for i in range(ORDERS_PER_PAGE + 5):
            make_order(name=f"Jordan Reyes {i}", archived=True)

        html = authenticated_client.get(
            reverse("order:archived_order_list"), {"q": "jordan"}
        ).content.decode()

        spinner = re.search(r'id="loading-spinner-row"\s+hx-get="([^"]+)"', html)
        assert spinner is not None
        # Must not fall back to the active-orders endpoint.
        assert reverse("order:archived_order_list") in spinner.group(1)
        assert "q=jordan" in spinner.group(1)

    def test_a_term_with_spaces_survives_the_url(self, authenticated_client):
        for i in range(ORDERS_PER_PAGE + 5):
            make_order(name=f"Jordan Reyes {i}")

        html = authenticated_client.get(
            reverse("order:order_list"), {"q": "jordan reyes"}
        ).content.decode()

        spinner = re.search(r'id="loading-spinner-row"\s+hx-get="([^"]+)"', html)
        assert spinner is not None
        # urlencoded rather than a raw space, which would truncate the query.
        assert " " not in spinner.group(1)

    def test_bad_page_number_does_not_error(self, authenticated_client):
        make_order(name="Jordan")

        response = authenticated_client.get(
            reverse("order:order_list"), {"page": "not-a-number"}
        )

        assert response.status_code == 200
