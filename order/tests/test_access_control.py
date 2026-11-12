"""
Access control for admin-only endpoints.

order_download shipped with no decorators at all, exposing every customer's
name, email, Venmo handle and order history to anonymous visitors. These tests
cover the whole admin surface so that cannot recur on another view.
"""
import pytest
from django.urls import reverse


# Every endpoint that exposes customer data or mutates the catalogue.
ADMIN_GET_VIEWS = [
    "order:order_dashboard",
    "order:order_list",
    "order:archived_order_list",
    "order:archived_orders",
    "order:order_download",
    "order:order_summary_download",
    "order:summary",
    "order:product_dashboard",
    "order:product_list",
    "order:product_create",
    "order:collection_dashboard",
    "order:collection_list",
    "order:collection_create",
    "order:product_color_create",
    "order:product_category_create",
]

ADMIN_POST_VIEWS = [
    "order:bulk_delete_orders",
    "order:bulk_archive_orders",
]


def is_blocked(response):
    """Admin views redirect anonymous users to login (or 403)."""
    if response.status_code in (401, 403):
        return True
    return response.status_code == 302 and "login" in response.url.lower()


@pytest.mark.django_db
@pytest.mark.parametrize("view_name", ADMIN_GET_VIEWS)
def test_anonymous_cannot_reach_admin_view(client, view_name):
    response = client.get(reverse(view_name))
    assert is_blocked(response), (
        f"{view_name} returned {response.status_code} to an anonymous user"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("view_name", ADMIN_POST_VIEWS)
def test_anonymous_cannot_post_to_admin_view(client, view_name):
    response = client.post(reverse(view_name))
    assert is_blocked(response)


@pytest.mark.django_db
@pytest.mark.parametrize("view_name", ADMIN_GET_VIEWS)
def test_logged_in_non_admin_cannot_reach_admin_view(client, regular_user, view_name):
    """A regular account is not enough; these require is_superuser."""
    client.force_login(regular_user)
    response = client.get(reverse(view_name))
    assert is_blocked(response), (
        f"{view_name} returned {response.status_code} to a non-admin user"
    )


@pytest.mark.django_db
class TestCustomerDataExports:
    """The exports carry the most sensitive payload, so they get their own cover."""

    def test_order_download_rejects_anonymous(self, client):
        response = client.get(reverse("order:order_download"))
        assert is_blocked(response)
        assert "spreadsheet" not in response.get("Content-Type", "")

    def test_order_download_rejects_non_admin(self, client, regular_user):
        client.force_login(regular_user)
        response = client.get(reverse("order:order_download"))
        assert is_blocked(response)

    def test_order_download_allows_admin(self, client, admin_user):
        client.force_login(admin_user)
        response = client.get(reverse("order:order_download"))
        assert response.status_code == 200
        assert "spreadsheet" in response.get("Content-Type", "")


@pytest.mark.django_db
class TestPublicStorefrontStillWorks:
    """The guard must not lock customers out of the shop."""

    @pytest.mark.parametrize("view_name", [
        "order:index", "order:about", "order:contact",
        "order:shopping_cart", "order:order_summary", "order:payment-cancel",
    ])
    def test_public_views_stay_open(self, client, view_name):
        assert client.get(reverse(view_name)).status_code == 200
