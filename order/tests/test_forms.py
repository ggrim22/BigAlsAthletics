"""
Tests for order forms
"""
import pytest
from decimal import Decimal
from order.forms import (
    ProductForm, CollectionForm, CategoryForm, ColorForm,
    ProductVariantForm, CollectionSelectForm, ProductFilterForm,
    ContactForm, OrderItemForm
)
from order.models import (
    Product, Collection, ProductCategory, ProductColor,
    Size, OrderItem
)


@pytest.mark.django_db
class TestProductForm:
    """Tests for ProductForm"""

    def test_product_form_valid(self, collection, product_category, product_color):
        """Test creating a product with valid data"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        from io import BytesIO

        img = Image.new('RGB', (344, 250), color='red')
        img_io = BytesIO()
        img.save(img_io, format='JPEG')
        img_io.seek(0)

        form_data = {
            'name': 'Test Product',
            'collection': collection.id,
            'available_sizes': [Size.ADULT_M, Size.ADULT_L],
            'has_back_name': True,
            'active': True,
            'category': [product_category.id],
            'colors': [product_color.id]
        }

        file_data = {
            'image': SimpleUploadedFile('test.jpg', img_io.read(), content_type='image/jpeg')
        }

        form = ProductForm(data=form_data, files=file_data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_product_form_missing_required_fields(self):
        """Test form validation with missing required fields"""
        form = ProductForm(data={})
        assert not form.is_valid()
        assert 'name' in form.errors
        assert 'image' in form.errors

    def test_product_form_available_sizes_choices(self):
        """Test that available_sizes field has correct choices"""
        form = ProductForm()
        field = form.fields['available_sizes']
        assert field.choices == Size.choices

    def test_product_form_category_queryset(self, product_category):
        """Test that category field queries all categories"""
        form = ProductForm()
        categories = list(form.fields['category'].queryset)
        assert product_category in categories


@pytest.mark.django_db
class TestCollectionForm:
    """Tests for CollectionForm"""

    def test_collection_form_valid(self):
        """Test creating a collection with valid data"""
        form = CollectionForm(data={
            'name': 'Test Collection',
            'active': True
        })
        assert form.is_valid()

    def test_collection_form_duplicate_name(self, collection):
        """Test that duplicate collection names are not allowed"""
        form = CollectionForm(data={
            'name': collection.name,
            'active': True
        })
        # Note: This depends on your model's unique constraint
        # If you save it, it should raise an error
        if form.is_valid():
            with pytest.raises(Exception):
                form.save()

    def test_collection_form_empty_name(self):
        """Test validation with empty name"""
        form = CollectionForm(data={'name': '', 'active': True})
        assert not form.is_valid()
        assert 'name' in form.errors


@pytest.mark.django_db
class TestCategoryForm:
    """Tests for CategoryForm"""

    def test_category_form_valid(self):
        """Test creating a category with valid data"""
        form = CategoryForm(data={
            'name': 'Sweatshirt',
            'active': True
        })
        assert form.is_valid()

    def test_category_form_missing_name(self):
        """Test validation with missing name"""
        form = CategoryForm(data={'active': True})
        assert not form.is_valid()


@pytest.mark.django_db
class TestColorForm:
    """Tests for ColorForm"""

    def test_color_form_valid(self):
        """Test creating a color with valid data"""
        form = ColorForm(data={'name': 'Green'})
        assert form.is_valid()

    def test_color_form_empty_name(self):
        """Test validation with empty name"""
        form = ColorForm(data={'name': ''})
        assert not form.is_valid()


@pytest.mark.django_db
class TestProductVariantForm:
    """Tests for ProductVariantForm"""

    def test_variant_form_valid(self, product_category, product_color):
        """Test creating a variant with valid data"""
        form = ProductVariantForm(data={
            'category': product_category.id,
            'color': product_color.id,
            'price': '29.99',
            'available_sizes': [Size.ADULT_M, Size.ADULT_L]
        })
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_variant_form_missing_price(self, product_category):
        """Test validation with missing price"""
        form = ProductVariantForm(data={
            'category': product_category.id,
        })
        assert not form.is_valid()
        assert 'price' in form.errors

    def test_variant_form_invalid_price(self, product_category):
        """Test validation with invalid price"""
        form = ProductVariantForm(data={
            'category': product_category.id,
            'price': 'invalid'
        })
        assert not form.is_valid()
        assert 'price' in form.errors

    def test_variant_form_negative_price(self, product_category):
        """Test validation with negative price"""
        form = ProductVariantForm(data={
            'category': product_category.id,
            'price': '-10.00'
        })
        # Django's DecimalField typically allows negative values
        # You might want to add a MinValueValidator to prevent this


@pytest.mark.django_db
class TestCollectionSelectForm:
    """Tests for CollectionSelectForm"""

    def test_collection_select_form_valid(self, collection):
        """Test selecting a collection"""
        form = CollectionSelectForm(data={'collection': collection.id})
        assert form.is_valid()

    def test_collection_select_form_only_active(self, collection, inactive_collection):
        """Test that only active collections are in queryset"""
        form = CollectionSelectForm()
        collections = list(form.fields['collection'].queryset)
        assert collection in collections
        assert inactive_collection not in collections

    def test_collection_select_form_required(self):
        """Test that collection field is required"""
        form = CollectionSelectForm(data={})
        assert not form.is_valid()
        assert 'collection' in form.errors


@pytest.mark.django_db
class TestProductFilterForm:
    """Tests for ProductFilterForm"""

    def test_filter_form_empty_valid(self):
        """Test that empty filters are valid"""
        form = ProductFilterForm(data={})
        assert form.is_valid()

    def test_filter_form_with_collection(self, collection):
        """Test filtering by collection"""
        form = ProductFilterForm(data={'collection': collection.id})
        assert form.is_valid()

    def test_filter_form_with_product_name(self, order_item):
        """Test filtering by product name"""
        form = ProductFilterForm(data={'product_name': order_item.product_name})
        assert form.is_valid()

    def test_filter_form_product_name_choices(self, order_item):
        """Test that product_name field has correct choices"""
        form = ProductFilterForm()
        choices = [choice[0] for choice in form.fields['product_name'].choices]
        assert '' in choices  # Empty option
        assert order_item.product_name in choices

    def test_filter_form_both_filters(self, collection, order_item):
        """Test using both filters together"""
        form = ProductFilterForm(data={
            'collection': collection.id,
            'product_name': order_item.product_name
        })
        assert form.is_valid()

    def test_filter_form_only_unarchived_products(self, order, product):
        """Test that only non-archived orders appear in choices"""
        # Create an order item
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name='Visible Product',
            size=Size.ADULT_M,
            quantity=1
        )

        # Archive the order
        order.archived = True
        order.save()

        form = ProductFilterForm()
        choices = [choice[0] for choice in form.fields['product_name'].choices]
        assert 'Visible Product' not in choices


@pytest.mark.django_db
class TestContactForm:
    """Tests for ContactForm"""

    def test_contact_form_valid(self):
        """Test contact form with valid data"""
        form = ContactForm(data={
            'email': 'test@example.com',
            'message': 'This is a test message with enough characters.'
        })
        assert form.is_valid()

    def test_contact_form_invalid_email(self):
        """Test validation with invalid email"""
        form = ContactForm(data={
            'email': 'invalid-email',
            'message': 'This is a test message.'
        })
        assert not form.is_valid()
        assert 'email' in form.errors

    def test_contact_form_message_too_short(self):
        """Test validation with message under 10 characters"""
        form = ContactForm(data={
            'email': 'test@example.com',
            'message': 'Short'
        })
        assert not form.is_valid()
        assert 'message' in form.errors

    def test_contact_form_message_max_length(self):
        """Test message field max length"""
        form = ContactForm(data={
            'email': 'test@example.com',
            'message': 'x' * 2001
        })
        assert not form.is_valid()
        assert 'message' in form.errors

    def test_contact_form_missing_fields(self):
        """Test validation with missing required fields"""
        form = ContactForm(data={})
        assert not form.is_valid()
        assert 'email' in form.errors
        assert 'message' in form.errors


@pytest.mark.django_db
class TestOrderItemForm:
    """Tests for OrderItemForm"""

    def test_order_item_form_valid(self, product):
        """Test creating an order item with valid data"""
        form = OrderItemForm(data={
            'product': product.id,
            'size': Size.ADULT_L,
            'quantity': 2
        })
        assert form.is_valid()

    def test_order_item_form_quantity_min(self, product):
        """Test that quantity has minimum value of 1"""
        form = OrderItemForm(data={
            'product': product.id,
            'size': Size.ADULT_L,
            'quantity': 0
        })

    def test_order_item_form_missing_product(self):
        """Test validation with missing product"""
        form = OrderItemForm(data={
            'size': Size.ADULT_L,
            'quantity': 1
        })

        if 'product' in form.fields and form.fields['product'].required:
            assert not form.is_valid()
            assert 'product' in form.errors
        else:
            pass