from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from products.models import Product

# Currency precision: 2 decimal places
CURRENCY_PRECISION = Decimal("0.01")


class Order(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, _("Pending")),
        (STATUS_PAID, _("Paid")),
        (STATUS_FAILED, _("Failed")),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders", verbose_name=_("User"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name=_("Status"))
    is_paid = models.BooleanField(default=False, verbose_name=_("Is paid"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name=_("Total amount"))

    class Meta:
        verbose_name = _("Order")
        verbose_name_plural = _("Orders")

    def __str__(self):
        return f"Order #{self.pk} - {self.user.username}"

    @property
    def total(self):
        # Keep for backwards compatibility; prefer stored total_amount
        return self.total_amount or sum(item.line_total for item in self.items.all())


class OrderItem(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_SHIPPED = "shipped"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, _("Pending")),
        (STATUS_PROCESSING, _("Processing")),
        (STATUS_SHIPPED, _("Shipped")),
        (STATUS_DELIVERED, _("Delivered")),
        (STATUS_CANCELLED, _("Cancelled")),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name=_("Order"))
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name=_("Product"))
    quantity = models.PositiveIntegerField(default=1, verbose_name=_("Quantity"))
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Price at purchase"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name=_("Status"))

    class Meta:
        verbose_name = _("Order Item")
        verbose_name_plural = _("Order Items")

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    @property
    def line_total(self):
        """Calculate line total with proper currency precision."""
        total = self.price_at_purchase * self.quantity
        return total.quantize(CURRENCY_PRECISION, rounding=ROUND_HALF_UP)

