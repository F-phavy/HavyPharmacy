from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

class Medicine(models.Model):
    CATEGORY_CHOICES = [
        ('Analgesics', 'Analgesics / Painkillers'),
        ('Antibiotics', 'Antibiotics'),
        ('Antimalarials', 'Antimalarials'),
        ('Vitamins', 'Vitamins & Supplements'),
        ('First Aid', 'First Aid'),
        ('General', 'General Items'),
    ]

    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, default='General')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=0)
    expiry_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    def __str__(self):
        return f"{self.name} - {self.sku}"

    def is_expiring_soon(self):
        # Logic to check if medicine expires within the next 30 days
        return self.expiry_date <= timezone.now().date() + timedelta(days=30)

class MedicineLog(models.Model):
    ACTION_CHOICES = [
        ('Restock', 'Restock'),
        ('Correction', 'Manual Correction'),
        ('Damage', 'Damaged/Expired Removal'),
        ('Sale', 'Sale'),
    ]

    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name='logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    quantity_changed = models.IntegerField() 
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.action} - {self.medicine.name} ({self.quantity_changed})"