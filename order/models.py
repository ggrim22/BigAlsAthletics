from django.db import models

class ProductCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Size(models.Model):
    SIZE_CHOICES = [
        ('XS', 'Youth XS'),
        ('YS', 'Youth Small'),
        ('YM', 'Youth Medium'),
        ('YL', 'Youth Large'),
        ('YXL', 'Youth XL'),
        ('AS', 'Adult Small'),
        ('AM', 'Adult Medium'),
        ('AL', 'Adult Large'),
        ('AXL', 'Adult XL'),
        ('2X', 'Adult 2X'),
        ('3X', 'Adult 3X'),
        ('4X', 'Adult 4X'),
    ]
    code = models.CharField(max_length=4, choices=SIZE_CHOICES, unique=True)

    def __str__(self):
        return self.code


class Collection(models.Model):
    name = models.CharField(max_length=200, unique=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE)
    collection = models.ForeignKey(
        Collection,
        on_delete=models.CASCADE,
        related_name="products",
        null=True,
        blank=True
    )
    name = models.CharField(max_length=200)
    color = models.CharField(max_length=50)
    image = models.ImageField(upload_to="products/")
    cost = models.DecimalField(max_digits=6, decimal_places=2)
    available_sizes = models.ManyToManyField(Size, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.color} {self.name}"


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

    # Denormalized snapshot fields
    product_name = models.CharField(max_length=200, blank=True, null=True)
    product_color = models.CharField(max_length=50, blank=True, null=True)
    product_cost = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    product_category = models.CharField(max_length=100, blank=True, null=True)
    collection_name = models.CharField(max_length=200, blank=True, null=True)

    size = models.ForeignKey(Size, on_delete=models.SET_NULL, null=True, blank=True)
    size_code = models.CharField(max_length=4, blank=True, null=True)

    quantity = models.PositiveIntegerField(default=1)

    def save(self, *args, **kwargs):
        if self.product:
            self.product_name = self.product.name
            self.product_color = self.product.color
            self.product_cost = self.product.cost
            self.product_category = self.product.category.name if self.product.category else None
            self.collection_name = self.product.collection.name if self.product.collection else None

        if self.size:
            self.size_code = self.size.code
        super().save(*args, **kwargs)
