"""
Tests for the collection modal's presentation.

The create/update modals share the product modal's shell so the admin screens
look like one system.  These tests pin the structure that styling depends on.
"""
import re

import pytest
from django.urls import reverse

# Classes the .product-modal stylesheet hangs off. The collection modal has no
# multi-select grids, so product-modal__choice-list is deliberately absent.
SHELL_CLASSES = [
    'product-modal',
    'product-modal__header',
    'product-modal__eyebrow',
    'product-modal__body',
    'product-modal__section',
    'product-modal__options',
    'product-modal__toggle-list',
    'product-modal__toggle',
    'product-modal__footer',
]


@pytest.fixture
def authenticated_client(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.mark.django_db
class TestCollectionModalMatchesProductModal:

    def _create(self, client):
        return client.get(reverse('order:collection_create')).content.decode()

    def _update(self, client, collection):
        return client.get(
            reverse('order:collection_update', args=[collection.id])
        ).content.decode()

    @pytest.mark.parametrize('css_class', SHELL_CLASSES)
    def test_create_modal_uses_product_modal_shell(
        self, authenticated_client, css_class
    ):
        assert css_class in self._create(authenticated_client)

    @pytest.mark.parametrize('css_class', SHELL_CLASSES)
    def test_update_modal_uses_product_modal_shell(
        self, authenticated_client, collection, css_class
    ):
        assert css_class in self._update(authenticated_client, collection)

    def test_shell_classes_are_the_ones_the_product_modal_uses(
        self, authenticated_client, product, collection
    ):
        """Guards against the stylesheet and the markup drifting apart"""
        product_html = authenticated_client.get(
            reverse('order:product_update', args=[product.id])
        ).content.decode()

        for css_class in SHELL_CLASSES:
            assert css_class in product_html, f"{css_class} is no longer a product-modal class"

    def test_modals_carry_their_own_titles(self, authenticated_client, collection):
        assert 'Create collection' in self._create(authenticated_client)
        assert 'Edit collection' in self._update(authenticated_client, collection)

    def test_footer_has_styled_cancel_and_submit(self, authenticated_client, collection):
        content = self._update(authenticated_client, collection)

        assert re.search(r'<button[^>]*class="btn btn-light"[^>]*>\s*Cancel', content)
        assert re.search(r'<button type="submit"[^>]*class="btn btn-dark[^"]*"', content)

    def test_body_is_split_into_both_section_cards(self, authenticated_client, collection):
        """Details + Options. Presence checks alone would pass with one missing."""
        content = self._update(authenticated_client, collection)

        sections = re.findall(r'<section class="product-modal__section[^"]*"', content)
        assert len(sections) == 2

    def test_name_sits_in_the_details_card_and_toggles_in_the_options_card(
        self, authenticated_client, collection
    ):
        content = self._update(authenticated_client, collection)

        cards = re.findall(
            r'<section class="product-modal__section[^"]*".*?</section>', content, re.DOTALL
        )
        assert len(cards) == 2
        details, options = cards

        assert 'name="name"' in details
        assert 'name="name"' not in options
        assert 'name="has_player_name"' in options
        assert 'name="active"' in options

    def test_name_field_renders_as_a_crispy_field(self, authenticated_client, collection):
        """Bootstrap form-control styling comes from crispy, not a bare input"""
        content = self._update(authenticated_client, collection)

        assert re.search(r'<input[^>]*name="name"[^>]*class="[^"]*form-control', content)

    def test_toggles_carry_the_bootstrap_checkbox_class(self, authenticated_client, collection):
        """.product-modal__toggle .form-check-input only applies with this class"""
        content = self._update(authenticated_client, collection)

        for field in ('has_player_name', 'active'):
            tag = re.search(rf'<input[^>]*name="{field}"[^>]*>', content)
            assert tag is not None, field
            assert 'form-check-input' in tag.group(), field

    def test_each_toggle_has_a_label_bound_to_it(self, authenticated_client, collection):
        content = self._update(authenticated_client, collection)

        for field in ('has_player_name', 'active'):
            assert f'<label for="id_{field}">' in content, field

    def test_help_text_reference_resolves(self, authenticated_client, collection):
        """A dangling aria-describedby would be an accessibility bug"""
        content = self._update(authenticated_client, collection)

        targets = re.findall(r'aria-describedby="([^"]+)"', content)
        assert targets, 'expected the player-name help text to be referenced'
        for target in targets:
            assert f'id="{target}"' in content, f'dangling aria-describedby: {target}'

    def test_modal_no_longer_dumps_the_whole_form(self, authenticated_client, collection):
        """The old `{{ form|crispy }}` render is what looked unstyled"""
        content = self._update(authenticated_client, collection)

        # crispy's whole-form render wraps fields in this; per-field render does not.
        assert 'product-modal__section' in content
        # The toggles must be hand-placed in the toggle list, not auto-rendered.
        toggle_list = re.search(
            r'product-modal__toggle-list.*?</section>', content, re.DOTALL
        )
        assert toggle_list is not None
        assert 'has_player_name' in toggle_list.group()
        assert 'active' in toggle_list.group()
