from django import forms
from django.core.validators import EmailValidator
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


class CollectionFilterForm(forms.Form):
    collection = forms.ModelChoiceField(
        queryset=Collection.objects.filter(active=True),
        required=False,
        label=None,
        empty_label="-- All Collections --",
        widget=forms.Select(attrs={
            "class": "form-select",
            "hx-get": "/orders/summary/",
            "hx-target": "#summary-table",
            "hx-trigger": "change",
            "hx-push-url": "true",
        })
    )


class ContactForm(forms.Form):
    email = forms.EmailField(
        max_length=254,
        required=True,
        validators=[EmailValidator(message="Please enter a valid email address.")],
        widget=forms.EmailInput(attrs={
            'placeholder': 'your.email@example.com',
            'class': 'w-full px-6 py-4 text-lg bg-stone-50 border-2 border-stone-200 rounded-2xl'
        })
    )

    message = forms.CharField(
        max_length=2000,
        required=True,
        widget=forms.Textarea(attrs={
            'placeholder': 'Tell us what\'s on your mind...',
            'rows': 8,
            'class': 'w-full px-6 py-4 text-lg bg-stone-50 border-2 border-stone-200 rounded-2xl'
        })
    )

    def clean_message(self):
        message = self.cleaned_data.get('message')
        if len(message) < 10:
            raise forms.ValidationError("Please provide a more detailed message (at least 10 characters).")
        return message


class ProductFilterForm(forms.Form):
    collection = forms.ModelChoiceField(
        queryset=Collection.objects.filter(active=True),
        required=False,
        label=None,
        empty_label="-- All Collections --",
        widget=forms.Select(attrs={
            "class": "form-select",
            "hx-get": "/orders/summary/",
            "hx-target": "#summary-table",
            "hx-trigger": "change",
            "hx-push-url": "true",
        })
    )

    product_name = forms.ChoiceField(
        required=False,
        label=None,
        widget=forms.Select(attrs={
            "class": "form-select",
            "hx-get": "/orders/summary/",
            "hx-target": "#summary-table",
            "hx-trigger": "change",
            "hx-push-url": "true",
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        product_names = OrderItem.objects.filter(
            order__archived=False
        ).values_list('product_name', flat=True).distinct().order_by('product_name')

        choices = [('', '-- All Products --')]
        choices.extend([(name, name) for name in product_names if name])

        self.fields['product_name'].choices = choices