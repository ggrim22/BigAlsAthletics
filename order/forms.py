from django import forms
from django.forms import modelformset_factory
from .models import OrderItem, Product, Collection, Size, ProductCategory, ProductColor, ProductVariant



class OrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ['product', 'size', 'quantity']
        widgets = {
            'quantity': forms.NumberInput(attrs={'min': 1}),
        }

OrderItemFormSet = modelformset_factory(
    OrderItem,
    form=OrderItemForm,
    extra=1,
    can_delete=True
)


class ProductVariantForm(forms.ModelForm):
    available_sizes = forms.MultipleChoiceField(
        choices=Size.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = ProductVariant
        fields = ["category", "price", "color"]

class ProductForm(forms.ModelForm):
    available_sizes = forms.MultipleChoiceField(
        choices=Size.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    category = forms.ModelMultipleChoiceField(
        queryset=ProductCategory.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    colors = forms.ModelMultipleChoiceField(
        queryset=ProductColor.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Product
        exclude = ['back_name']


class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = '__all__'


class CategoryForm(forms.ModelForm):
    class Meta:
        model = ProductCategory
        fields = '__all__'


class ColorForm(forms.ModelForm):
    class Meta:
        model = ProductColor
        fields = '__all__'


class CollectionSelectForm(forms.Form):
    collection = forms.ModelChoiceField(
        queryset=Collection.objects.filter(active=True),
        required=True,
        label="Select a Collection",
        widget=forms.Select(attrs={"class": "form-select"})
    )
