import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

# Import everything from each app in one line
from inventory.models import Medicine, MedicineLog
from .models import Sale, SaleItem
from accounts.models import Attendance
import uuid # Add this at the top
from django.views.decorators.cache import never_cache

@login_required
@never_cache
def pos_view(request):
    # 1. ATTENDANCE CHECK: Look for an open session (no clock_out yet)
    active_session = Attendance.objects.filter(
        user=request.user,
        clock_out__isnull=True
    ).exists()

    if request.method == 'POST':
        # 🔒 THE SECURITY FIX: If they aren't clocked in, block the sale immediately!
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
        
    medicines = Medicine.objects.filter(quantity__gt=0).order_by('name')
    
    return render(request, 'sales/pos.html', {
        'medicines': medicines,
        'needs_attendance': not active_session  
    })


def stock_list(request):
    # Fetch all medicines
    medicines = Medicine.objects.all().order_by('name')
    
    # Logic for summary stats
    low_stock_threshold = 10
    low_stock_count = medicines.filter(quantity__lt=low_stock_threshold).count()
    
    context = {
        'medicines': medicines,
        'low_stock_count': low_stock_count,
        'threshold': low_stock_threshold,
    }
    return render(request, 'sales/stock_list.html', context) 

def receipt_view(request, sale_id):
    # Fetching the sale and its items for the printable receipt
    sale = get_object_or_404(Sale.objects.prefetch_related('items'), id=sale_id)
    return render(request, 'sales/receipt.html', {'sale': sale})

@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        return redirect('pos_view')

    today = timezone.now().date()
    medicines = Medicine.objects.all().order_by('name')
    
    # 1. Financial Logic
    sales_today = Sale.objects.filter(timestamp__date=today)
    daily_revenue = sales_today.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    
    # Calculate Profit: Total of (SaleItem subtotal - (Medicine Cost * Quantity))
    daily_profit = 0
    sale_items = SaleItem.objects.filter(sale__timestamp__date=today)
    for item in sale_items:
        daily_profit += (item.subtotal - (item.medicine.cost_price * item.quantity))

    # Build chart data for last 7 days
    labels = []
    sales_data = []
    profit_data = []
    
    for i in range(6, -1, -1):  # Last 7 days
        date = timezone.now().date() - timedelta(days=i)
        labels.append(date.strftime('%b %d')) # e.g., "May 18"
        
        # Daily revenue
        daily_total = Sale.objects.filter(timestamp__date=date).aggregate(
            Sum('total_amount'))['total_amount__sum'] or 0
        sales_data.append(float(daily_total))
        
        # Daily profit
        daily_profit_total = 0
        profit_items = SaleItem.objects.filter(sale__timestamp__date=date)
        for item in profit_items:
            daily_profit_total += (item.subtotal - (item.medicine.cost_price * item.quantity))
        profit_data.append(float(daily_profit_total))

    # Get recent sales for activity feed
    sales_history = Sale.objects.all().order_by('-timestamp')[:10]
    
    # Count active users with open sessions
    active_users = Attendance.objects.filter(clock_out__isnull=True).values('user').distinct().count()

    context = {
        'medicines': medicines,
        'daily_sales': daily_revenue,
        'daily_profit': daily_profit,
        'low_stock_count': medicines.filter(quantity__lte=5).count(),
        'stock_history': MedicineLog.objects.all().order_by('-timestamp')[:10],
        'today': today,
        'chart_labels': json.dumps(labels),
        'sales_chart_data': json.dumps(sales_data),
        'profit_chart_data': json.dumps(profit_data),
        'sales_history': sales_history,
        'active_users_count': active_users,
    }
    return render(request, 'accounts/admin_dashboard.html', context)
@login_required
def add_medicine(request):
    if not request.user.is_staff:
        return redirect('pos_view')

    if request.method == 'POST':
        name = request.POST.get('name')
        category = request.POST.get('category')
        cost_price = request.POST.get('cost_price')
        price = request.POST.get('price')
        quantity = request.POST.get('quantity')

        # Create the new medicine record
        new_med = Medicine.objects.create(
            name=name,
            category=category,
            cost_price=cost_price,
            price=price,
            quantity=quantity
        )

        # Create a log entry for the Audit Trail
        MedicineLog.objects.create(
            medicine=new_med,
            user=request.user,
            action='Stock Added',
            quantity_changed=quantity,
            notes="Initial entry via Admin Dashboard"
        )

        messages.success(request, f"{name} added to inventory!")
        return redirect('admin_dashboard') # Or whatever your dashboard URL name is