import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import uuid 
from django.views.decorators.cache import never_cache

# Import models
from inventory.models import Medicine, MedicineLog
from .models import Sale, SaleItem
from accounts.models import Attendance

@login_required
@never_cache
def pos_view(request):
    today = timezone.now().date()
    active_session = Attendance.objects.filter(
        user=request.user,
        clock_out__isnull=True
    ).exists()

    if request.method == 'POST':
        if not active_session:
            messages.error(request, "Access Denied: You must clock in before processing sales!")
            return redirect('pos_view')

        cart_data_json = request.POST.get('cart_data')
        if not cart_data_json or cart_data_json == "[]":
            messages.error(request, "Your cart is empty!")
            return redirect('pos_view')
            
        try:
            cart_items = json.loads(cart_data_json)
            with transaction.atomic():
                t_id = f"TRX-{uuid.uuid4().hex[:8].upper()}"
                current_sale = Sale.objects.create(
                    transaction_id=t_id,
                    salesperson=request.user,
                    total_amount=0 
                )
                running_total = 0
                for item in cart_items:
                    medicine = Medicine.objects.select_for_update().get(id=item['id'])
                    quantity = int(item['quantity'])
                    
                    if medicine.quantity >= quantity:
                        item_subtotal = medicine.price * quantity
                        SaleItem.objects.create(
                            sale=current_sale,
                            medicine=medicine,
                            quantity=quantity,
                            unit_price=medicine.price,
                            subtotal=item_subtotal
                        )
                        medicine.quantity -= quantity
                        medicine.save()
                        MedicineLog.objects.create(
                            medicine=medicine,
                            user=request.user,
                            action='Sale',
                            quantity_changed=-quantity,
                            notes=f"Sold in {t_id}"
                        )
                        running_total += item_subtotal
                    else:
                        raise ValueError(f"Not enough stock for {medicine.name}!")
                
                current_sale.total_amount = running_total
                current_sale.save()
            messages.success(request, f"Sale {t_id} successful!")
            return redirect('receipt_view', sale_id=current_sale.id)
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('pos_view')
    
    # Corrected: Filter out expired items in POS
    medicines = Medicine.objects.filter(quantity__gt=0, expiry_date__gte=today).order_by('name')
    
    return render(request, 'sales/pos.html', {
        'medicines': medicines,
        'needs_attendance': not active_session  
    })

def stock_list(request):
    today = timezone.now().date()
    # Corrected: Only show non-expired items
    medicines = Medicine.objects.filter(expiry_date__gte=today).order_by('name')
    low_stock_threshold = 10
    low_stock_count = medicines.filter(quantity__lt=low_stock_threshold).count()
    
    context = {
        'medicines': medicines,
        'low_stock_count': low_stock_count,
        'threshold': low_stock_threshold,
    }
    return render(request, 'sales/stock_list.html', context) 

def receipt_view(request, sale_id):
    sale = get_object_or_404(Sale.objects.prefetch_related('items'), id=sale_id)
    return render(request, 'sales/receipt.html', {'sale': sale})

@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        return redirect('pos_view')

    today = timezone.now().date()
    
    # Corrected: Split querysets
    all_meds = Medicine.objects.all().order_by('name')
    active_medicines = all_meds.filter(expiry_date__gte=today)
    expired_medicines = all_meds.filter(expiry_date__lt=today)
    
    # Financial Logic
    sales_today = Sale.objects.filter(timestamp__date=today)
    daily_revenue = sales_today.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    daily_profit = 0
    for item in SaleItem.objects.filter(sale__timestamp__date=today):
        daily_profit += (item.subtotal - (item.medicine.cost_price * item.quantity))

    # Chart Data
    labels, sales_data, profit_data = [], [], []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        labels.append(d.strftime('%b %d'))
        
        daily_total = Sale.objects.filter(timestamp__date=d).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        sales_data.append(float(daily_total))
        
        daily_p = sum((item.subtotal - (item.medicine.cost_price * item.quantity)) 
                      for item in SaleItem.objects.filter(sale__timestamp__date=d))
        profit_data.append(float(daily_p))

    context = {
        'medicines': active_medicines, # Main table now only shows active
        'expired_medicines': expired_medicines, # You can now iterate this in your template
        'daily_sales': daily_revenue,
        'daily_profit': daily_profit,
        'low_stock_count': active_medicines.filter(quantity__lte=5).count(),
        'stock_history': MedicineLog.objects.all().order_by('-timestamp')[:10],
        'today': today,
        'chart_labels': json.dumps(labels),
        'sales_chart_data': json.dumps(sales_data),
        'profit_chart_data': json.dumps(profit_data),
        'sales_history': Sale.objects.all().order_by('-timestamp')[:10],
        'active_users_count': Attendance.objects.filter(clock_out__isnull=True).values('user').distinct().count(),
    }
    return render(request, 'accounts/admin_dashboard.html', context)

@login_required
def add_medicine(request):
    if not request.user.is_staff:
        return redirect('pos_view')
    if request.method == 'POST':
        new_med = Medicine.objects.create(
            name=request.POST.get('name'),
            category=request.POST.get('category'),
            cost_price=request.POST.get('cost_price'),
            price=request.POST.get('price'),
            quantity=request.POST.get('quantity')
        )
        MedicineLog.objects.create(
            medicine=new_med,
            user=request.user,
            action='Stock Added',
            quantity_changed=request.POST.get('quantity'),
            notes="Initial entry via Admin Dashboard"
        )
        messages.success(request, f"{new_med.name} added!")
        return redirect('admin_dashboard')