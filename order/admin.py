from django.contrib import admin

from .models import Order, ProductCategory, Product, Size, OrderItem, Collection

# Register your models here.
admin.site.register(Order)
admin.site.register(ProductCategory)
admin.site.register(Product)
admin.site.register(Size)
admin.site.register(OrderItem)
admin.site.register(Collection)


