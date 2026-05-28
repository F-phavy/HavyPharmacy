from django.db import models
from django.conf import settings
from django.utils import timezone

# Assuming your existing product model looks similar to this:
class Medicine(models.Model):
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=0)
    expiry_date = models.DateField(null=True, blank=True)
    # ... any other fields you already have ...

    def __str__(self):
        return self.name


class Sale(models.Model):
    PAYMENT_METHODS = [
        ('CASH', 'Cash'),
        ('TRANSFER', 'Bank Transfer'),
        ('CARD', 'POS Card'),
    ]

    invoice_number = models.CharField(max_length=50, unique=True, editable=False)
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(default=timezone.now)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    payment_method = models.CharField(max_length=15, choices=PAYMENT_METHODS, default='CASH')

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            # Generates a clean, professional invoice prefix: HVY-20260527-153045
            self.invoice_number = f"HVY-{timezone.now().strftime('%Y%m%d-%H%M%S')}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invoice {self.invoice_number} - ₦{self.total_amount}"


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    medicine = models.ForeignKey(Medicine, on_delete=models.PROTECT) # Protect ensures inventory logs aren't accidentally wiped
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.subtotal = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity}x {self.medicine.name} inside {self.sale.invoice_number}"