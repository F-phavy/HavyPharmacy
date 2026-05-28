from django.contrib import admin
from .models import Medicine, MedicineLog

@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    # What columns show up in the table
    list_display = ('name', 'category', 'price', 'quantity', 'is_low_stock')
    
    # Allows you to edit price/stock without leaving the list page
    list_editable = ('price', 'quantity')
    
    # Search bar filters
    search_fields = ('name', 'category')
    list_filter = ('category',)

    # Custom color-coding for stock levels
    @admin.display(description="Status")
    def is_low_stock(self, obj):
        if obj.quantity <= 0:
            return "❌ Out of Stock"
        if obj.quantity < 10:
            return "⚠️ Low Stock"
        return "✅ Sufficient"

@admin.register(MedicineLog)
class MedicineLogAdmin(admin.ModelAdmin):
    list_display = ('medicine', 'action', 'quantity_changed', 'user', 'timestamp')
    readonly_fields = ('timestamp', 'user') # Prevent tampering with logs

    # This magic method sets the 'user' field to the logged-in admin automatically
    def save_model(self, request, obj, form, change):
        if not obj.pk:  # Only set the user when the log is first created
            obj.user = request.user
        super().save_model(request, obj, form, change)