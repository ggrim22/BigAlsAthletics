"""
Tests for the dashboard order count and the clickable modal choice rows.
"""
import io
import re

import pytest
from django.urls import reverse

from order.models import Order


@pytest.fixture
def authenticated_client(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.mark.django_db
class TestDashboardOrderCount:

    def test_count_appears_beside_the_heading(self, authenticated_client):
        for i in range(3):
            Order.objects.create(customer_name=f"C{i}", customer_email=f"c{i}@x.com")

        content = authenticated_client.get(reverse("order:order_dashboard")).content.decode()

        heading = re.search(r"<h3[^>]*>(.*?)</h3>", content, re.DOTALL)
        assert heading is not None
        assert "Order Dashboard" in heading.group(1)
        assert "3 orders" in heading.group(1)

    def test_count_is_muted(self, authenticated_client):
        Order.objects.create(customer_name="C", customer_email="c@x.com")

        content = authenticated_client.get(reverse("order:order_dashboard")).content.decode()

        span = re.search(r'<span class="([^"]*)">\s*\d+ orders?\s*</span>', content)
        assert span is not None
        classes = span.group(1)
        assert "text-zinc-500" in classes, "count should be muted, not full-contrast"
        assert "font-normal" in classes, "count should not inherit the heading weight"

    def test_count_excludes_archived(self, authenticated_client):
        Order.objects.create(customer_name="Active", customer_email="a@x.com")
        Order.objects.create(customer_name="Gone", customer_email="g@x.com", archived=True)

        content = authenticated_client.get(reverse("order:order_dashboard")).content.decode()

        assert "1 order<" in content or "1 order " in content
        assert "2 order" not in content

    def test_singular_and_plural(self, authenticated_client):
        Order.objects.create(customer_name="Only", customer_email="o@x.com")
        content = authenticated_client.get(reverse("order:order_dashboard")).content.decode()
        assert "1 order" in content and "1 orders" not in content


class TestModalRowsAreClickable:
    """The rows already highlight on hover, so the whole row must be the hit area."""

    @pytest.fixture
    def css(self):
        with io.open("static/css/style.css", encoding="utf-8") as handle:
            return handle.read()

    def test_choice_rows_are_positioned(self, css):
        """A stretched overlay needs a positioned ancestor"""
        block = re.search(
            r"\.product-modal #div_id_category \.form-check,.*?\{(.*?)\}", css, re.DOTALL
        )
        assert block is not None
        assert "position: relative" in block.group(1)

    def test_choice_labels_stretch_over_the_whole_row(self, css):
        assert ".product-modal #div_id_category .form-check-label::before" in css
        block = re.search(
            r"\.product-modal #div_id_category \.form-check-label::before,.*?\{(.*?)\}",
            css, re.DOTALL,
        )
        assert block is not None
        body = block.group(1)
        assert "position: absolute" in body
        assert "inset: 0" in body

    def test_toggle_rows_are_clickable_too(self, css):
        block = re.search(r"\.product-modal__toggle \{(.*?)\}", css, re.DOTALL)
        assert block is not None and "position: relative" in block.group(1)

        overlay = re.search(r"\.product-modal__toggle label::before \{(.*?)\}", css, re.DOTALL)
        assert overlay is not None
        assert "position: absolute" in overlay.group(1)
        assert "inset: 0" in overlay.group(1)


@pytest.mark.django_db
class TestModalMarkupSupportsClicking:

    def test_every_choice_label_is_bound_to_its_input(self, authenticated_client, product):
        """The overlay only works because the label targets the checkbox"""
        content = authenticated_client.get(
            reverse("order:product_update", args=[product.id])
        ).content.decode()

        labels = re.findall(r'<label[^>]*for="(id_category_\d+)"', content)
        assert labels, "expected crispy to bind category labels to inputs"
        for target in labels:
            assert f'id="{target}"' in content, f"label points at missing input {target}"
