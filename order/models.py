from decimal import Decimal

from django.db import models

class ProductCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class ProductColor(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Size(models.TextChoices):
    YOUTH_XS = 'XS', 'Youth XS'
    YOUTH_S = 'YS', 'Youth Small'
    YOUTH_M = 'YM', 'Youth Medium'
    YOUTH_L = 'YL', 'Youth Large'
    YOUTH_XL = 'YXL', 'Youth XL'
    ADULT_S = 'AS', 'Adult Small'
    ADULT_M = 'AM', 'Adult Medium'
    ADULT_L = 'AL', 'Adult Large'
    ADULT_XL = 'AXL', 'Adult XL'
    ADULT_2X = '2X', 'Adult 2X'
    ADULT_3X = '3X', 'Adult 3X'
    ADULT_4X = '4X', 'Adult 4X'
    ADULT_5X = '5X', 'Adult 5X'
    ONE_SIZE = 'One Size', 'One Size'


class Collection(models.Model):
    name = models.CharField(max_length=200, unique=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ManyToManyField(ProductCategory, related_name="products", blank=True)
    collection = models.ForeignKey(
        Collection,
        on_delete=models.CASCADE,
        related_name="products",
        null=True,
        blank=True
    )
    colors = models.ManyToManyField(
        ProductColor,
        related_name="products",
        blank=True
    )
    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to="products/")
    available_sizes = models.JSONField(default=list)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.colors} {self.name}"

    @property
    def get_available_sizes(self):
        return [(size, Size(size).label) for size in self.available_sizes]

class Order(models.Model):
    customer_name = models.CharField(max_length=100, blank=True, verbose_name='Name')
    customer_email = models.CharField(max_length=100, blank=True, verbose_name='Email')
    customer_venmo = models.CharField(max_length=100, blank=True, verbose_name='Venmo Username')
    created_at = models.DateTimeField(auto_now_add=True)
    has_paid = models.BooleanField(default=False)

    def __str__(self):
        return f"Order #{self.id} by {self.customer_name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)

    product_name = models.CharField(max_length=200, blank=True, null=True)
    product_color = models.CharField(max_length=50, blank=True, null=True)
    product_cost = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    product_category = models.CharField(max_length=100, blank=True, null=True)
    collection_name = models.CharField(max_length=200, blank=True, null=True)

    size = models.CharField(choices=Size.choices, blank=True)
    quantity = models.PositiveIntegerField(default=1)

    category_id = models.PositiveIntegerField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.product:
            self.product_name = self.product.name

            variant = None
            if self.product_category:
                try:
                    cat_id = int(self.product_category)
                    from .models import ProductCategory
                    category = ProductCategory.objects.filter(id=cat_id).first()
                except (ValueError, TypeError):
                    category = None

                if not category:
                    from .models import ProductCategory
                    category = ProductCategory.objects.filter(name=self.product_category).first()

                if category:
                    variant = self.product.variants.filter(category=category).first()
                    self.product_category = category.name

            if not variant:
                first_variant = self.product.variants.first()
                if first_variant:
                    variant = first_variant
                    if not self.product_category:
                        self.product_category = first_variant.category.name

            if variant:
                if not self.product_cost:
                    self.product_cost = variant.price
            else:
                if not self.product_cost:
                    self.product_cost = Decimal("0.00")

            self.collection_name = self.product.collection.name if self.product.collection else None

        super().save(*args, **kwargs)


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    color = models.ForeignKey(ProductColor, on_delete=models.SET_NULL, null=True, blank=True)
    available_sizes = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'category', 'color'],
                name='unique_product_variant'
            )
        ]

    def __str__(self):
        return f"{self.product.name} - {self.category.name} (${self.price})"