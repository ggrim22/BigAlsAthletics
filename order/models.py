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
        return dict(self.SIZE_CHOICES).get(self.code, self.code)

class Product(models.Model):
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    color = models.CharField(max_length=50)
    image = models.ImageField(upload_to="media/products/")
    cost = models.DecimalField(max_digits=6, decimal_places=2)
    available_sizes = models.ManyToManyField(Size, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.color} {self.name}"

class Organization(models.Model):
    name = models.CharField(max_length=200, unique=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Order(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="orders",
        null=True,
        blank=True
    )
    customer_name = models.CharField(max_length=100, blank=True, verbose_name='Name')
    customer_email = models.CharField(max_length=100, blank=True, verbose_name='Email')
    customer_venmo = models.CharField(max_length=100, blank=True, verbose_name='Venmo Username')
    created_at = models.DateTimeField(auto_now_add=True)
    has_paid = models.BooleanField(default=False)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    size = models.ForeignKey(Size, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
