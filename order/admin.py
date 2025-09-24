from django import forms
from django.contrib import admin

from .models import Order, ProductCategory, Product, Size, OrderItem, Collection

# Register your models here.
admin.site.register(Order)
admin.site.register(ProductCategory)
admin.site.register(OrderItem)
admin.site.register(Collection)


class ProductAdminForm(forms.ModelForm):
    available_sizes = forms.MultipleChoiceField(
        choices=Size.choices,
        widget=forms.CheckboxSelectMultiple(),
        required=False,
    )

    class Meta:
        model = Product
        fields = "__all__"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
