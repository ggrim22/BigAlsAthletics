# order/forms.py
from django import forms
from django.forms import modelformset_factory
from .models import OrderItem, Product, Collection, Size


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


class ProductForm(forms.ModelForm):
    available_sizes = forms.MultipleChoiceField(
        choices=Size.choices,
        widget=forms.CheckboxSelectMultiple(),
        required=False,
    )

    class Meta:
        model = Product
        fields = '__all__'


class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = '__all__'

