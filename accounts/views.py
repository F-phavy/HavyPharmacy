import json
import csv
import datetime
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, F  # <--- FIXED: Added F here
from django.http import HttpResponse

# Cross-app explicit model imports
from inventory.models import Medicine  
from sales.models import Sale, SaleItem  
from .models import Attendance, User
from .forms import HavySignUpForm  

# Form import for inventory management
from inventory.forms import MedicineForm 


def landing_page(request):
    return render(request, 'home.html')    

# ==========================================
# 1. THE SIGNUP VIEW
# ==========================================
def signup_view(request):
    if request.method == 'POST':
        form = HavySignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            if user.role == 'Salesperson':
                return redirect('sales_dashboard')
            return redirect('dashboard')
        else:
            print(form.errors) 
    else:
        form = HavySignUpForm()
    return render(request, 'registration/signup.html', {'form': form})

# ==========================================
# 2. THE LOGOUT VIEW
# ==========================================
def logout_view(request):
    logout(request)
    return redirect('login')

# ==========================================
# 3. THE UPDATED ADMIN DASHBOARD VIEW
# ==========================================
@login_required
def dashboard(request):
    if request.user.role != 'Admin' and not request.user.is_staff:
        return redirect('sales_dashboard')

    today = timezone.now().date()
    medicines = Medicine.objects.all().order_by('name')
    
    active_staff = Attendance.objects.filter(clock_out__isnull=True).select_related('user')
    completed_shifts = Attendance.objects.filter(date=today, clock_out__isnull=False).select_related('user')

    # STAFF SHIFT EARNINGS LOGIC
    all_todays_attendance = Attendance.objects.filter(date=today).select_related('user')
    staff_earnings_history = []

    # ONLY ONE LOOP HERE
    for record in all_todays_attendance:
        buffer_start = record.clock_in - timedelta(minutes=1)
        
        # Calculate sales for THIS specific staff member
        sales_query = Sale.objects.filter(
            salesperson=record.user,
            timestamp__gte=buffer_start
        )
        
        # If they finished their shift, cap the sales at their clock_out time
        if record.clock_out:
            sales_query = sales_query.filter(timestamp__lte=record.clock_out)
        
        # Aggregate the total
        total_earned = sales_query.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    
        staff_earnings_history.append({
            'user_id': record.user.id,
            'staff_name': record.user.get_full_name() or record.user.username,
            'clock_in': record.clock_in,
            'clock_out': record.clock_out,
            'total_earned': total_earned,
            'is_active': record.clock_out is None
        })

    # Financial Analytics
    daily_sales = Sale.objects.filter(timestamp__date=today).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    
    daily_profit = 0
    today_items = SaleItem.objects.filter(sale__timestamp__date=today).select_related('medicine')
    for item in today_items:
        cost_price = item.medicine.cost_price if hasattr(item.medicine, 'cost_price') and item.medicine.cost_price else 0
        daily_profit += (item.subtotal - (cost_price * item.quantity))

    # Optimized 7-Day Timeline Dataset
    labels = []
    sales_chart_data = []
    profit_chart_data = []
    
    start_date = today - timedelta(days=6)
    weekly_sales = list(Sale.objects.filter(timestamp__date__range=[start_date, today]))
    weekly_items = list(SaleItem.objects.filter(sale__timestamp__date__range=[start_date, today]).select_related('medicine', 'sale'))

    for i in range(6, -1, -1):
        target_date = today - timedelta(days=i)
        labels.append(target_date.strftime('%b %d'))
        
        day_revenue = sum([s.total_amount for s in weekly_sales if s.timestamp.date() == target_date])
        sales_chart_data.append(float(day_revenue))
        
        day_profit = 0
        for item in weekly_items:
            if item.sale.timestamp.date() == target_date:
                cost = item.medicine.cost_price if hasattr(item.medicine, 'cost_price') and item.medicine.cost_price else 0
                day_profit += (item.subtotal - (cost * item.quantity))
        profit_chart_data.append(float(day_profit))

    context = {
        'medicines': medicines,
        'daily_sales': daily_sales,
        'daily_profit': daily_profit,
        'low_stock_count': medicines.filter(quantity__lte=5).count(),
        'stock_history': Sale.objects.filter(timestamp__date=today).order_by('-timestamp')[:10],
        'chart_labels': json.dumps(labels),
        'sales_chart_data': json.dumps(sales_chart_data),
        'profit_chart_data': json.dumps(profit_chart_data),
        'active_staff': active_staff,
        'completed_shifts': completed_shifts,
        'staff_earnings_history': staff_earnings_history,
    }
    return render(request, 'accounts/admin_dashboard.html', context)

# ==========================================
# 4. THE SALESPERSON DASHBOARD
# ==========================================
@login_required
def sales_dashboard(request):
    today = timezone.now().date()
    
    # Isolate Gross Revenue metrics to the logged-in user
    user_daily_total = Sale.objects.filter(
        salesperson=request.user,
        timestamp__date=today
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    low_stock_count = Medicine.objects.filter(quantity__lt=10).count()
    recent_attendance = Attendance.objects.filter(user=request.user).order_by('-clock_in')[:5]
    attendance = Attendance.objects.filter(user=request.user, date=today).first()

    remaining_seconds = 0
    if attendance and attendance.clock_out is None:
        shift_duration = timedelta(hours=8)
        end_time = attendance.clock_in + shift_duration
        now = timezone.now()
        if end_time > now:
            remaining_seconds = int((end_time - now).total_seconds())

    # Fetch recent items sold today ONLY by this logged-in salesperson
    recent_sales = SaleItem.objects.filter(
        sale__salesperson=request.user,  # <--- FIXED: Isolation filter added
        sale__timestamp__date=today
    ).select_related('sale', 'medicine').order_by('-sale__timestamp')[:10]

    # Calculate Top-Selling Medicines for today ONLY by this logged-in salesperson
    top_products = SaleItem.objects.filter(
        sale__salesperson=request.user,  # <--- FIXED: Isolation filter added
        sale__timestamp__date=today
    ).values(
        'medicine__name'
    ).annotate(
        total_sold=Sum('quantity'),
        total_revenue=Sum('subtotal')  
    ).order_by('-total_sold')[:5]

    context = {
        'recent_attendance': recent_attendance,
        'day_name': timezone.now().strftime('%A'),
        'date_full': timezone.now().strftime('%d %B %Y'),
        'user_daily_total': user_daily_total,
        'low_stock_count': low_stock_count,
        'remaining_seconds': remaining_seconds,
        'attendance': attendance,
        'recent_sales': recent_sales,
        'top_products': top_products,
    }
    return render(request, 'accounts/sales_dashboard.html', context)
# ==========================================
# 5. ATTENDANCE MECHANICS (RESTORED)
# ==========================================

@login_required
def mark_attendance(request):
    if request.method != 'POST':
        return redirect('sales_dashboard')

    today = timezone.now().date()
    now = timezone.now()
    action = request.POST.get('action')
    
    # Get or create today's attendance record
    attendance, created = Attendance.objects.get_or_create(user=request.user, date=today)

    if action == 'clock_in':
        # First time clocking in OR coming back from a break
        if attendance.status in ['inactive', 'break']:
            if not attendance.clock_in:
                attendance.clock_in = now  # Only set initial clock-in once
            attendance.status = 'active'
            attendance.save()
            messages.success(request, "You are now checked in and Active!")

    elif action == 'go_on_break':
        if attendance.status == 'active':
            attendance.status = 'break'
            attendance.save()
            messages.warning(request, "You are now on a break. System access paused.")
            # Optional: Log them out automatically so they are no longer active
            # auth_logout(request)
            # return redirect('login')

    elif action == 'clock_out':
        # End shift completely for the day
        if attendance.status in ['active', 'break']:
            attendance.clock_out = now
            attendance.status = 'inactive'
            attendance.save()
            messages.success(request, "Shift completed successfully! Goodbye.")
            
    return redirect('sales_dashboard')
# ==========================================
# 6. INVENTORY ADD PRODUCT VIEW (FINAL PROVISIONED)
# ==========================================
@login_required
def add_product_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        sku = request.POST.get('sku') # Aligned perfectly with template name="sku"
        category = request.POST.get('category', 'General')
        quantity = request.POST.get('quantity', 0)
        cost_price = request.POST.get('cost_price', 0.00)
        price = request.POST.get('price', 0.00)
        expiry_input = request.POST.get('expiry_date')

        # Clean string inputs to date objects safely
        try:
            if expiry_input:
                parsed_expiry = datetime.datetime.strptime(expiry_input, "%Y-%m-%d").date()
            else:
                parsed_expiry = timezone.now().date() + timedelta(days=365)
        except Exception:
            parsed_expiry = timezone.now().date() + timedelta(days=365)

        # Sanitize float values to prevent schema violations
        try:
            qty_val = int(quantity) if quantity else 0
            cost_val = float(cost_price) if cost_price else 0.00
            price_val = float(price) if price else 0.00
        except ValueError:
            messages.error(request, "Format validation failed on numeric parameters.")
            return render(request, 'inventory/add_product.html')

        if name and sku:
            try:
                Medicine.objects.create(
                    name=name,
                    sku=sku,
                    category=category,
                    quantity=qty_val,
                    cost_price=cost_val,
                    price=price_val,
                    expiry_date=parsed_expiry
                )
                messages.success(request, f"Asset '{name}' registered successfully.")
                return redirect('dashboard') # Triggers immediate redirect to dashboard
            except Exception as database_error:
                messages.error(request, f"Database transaction rejected: {str(database_error)}")
        else:
            messages.error(request, "Failed submission: Identification values missing.")
            
    return render(request, 'inventory/add_product.html')
# ==========================================
# 7. EXPORT SHIFT SUMMARY (CSV)
# ==========================================

@login_required
def export_shift_summary(request):
    # Security check: Ensure only Admin or Staff can access this download
    if not request.user.is_staff and getattr(request.user, 'role', None) != 'Admin':
        messages.error(request, "Access Denied: Admin privileges required.")
        return redirect('pos_view')

    today = timezone.now().date()

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="admin_global_shift_{today}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Transaction/Sale ID', 'Salesperson', 'Total Bill Amount', 'Timestamp'])
    
    # 🛠️ FIXED: Removed 'cashier' optimization since the model only uses 'salesperson'
    sales = Sale.objects.filter(timestamp__date=today).select_related('salesperson')
        
    for sale in sales:
        # 🛠️ FIXED: Reference the correct salesperson field directly
        staff_username = sale.salesperson.username if sale.salesperson else "Unknown"
        
        sale_identifier = sale.transaction_id if hasattr(sale, 'transaction_id') else sale.id
        
        writer.writerow([
            sale_identifier, 
            staff_username, 
            sale.total_amount, 
            sale.timestamp.strftime('%H:%M:%S')
        ])
        
    return response


@user_passes_test(lambda u: u.is_staff or u.role == 'admin')
def admin_reset_attendance(request, user_id):
    if request.method == "POST":
        target_user = get_object_or_404(User, id=user_id)
        today = timezone.now().date()
        
        # Find today's attendance record for this salesperson
        attendance = Attendance.objects.filter(user=target_user, date=today).first()
        
        if attendance:
            attendance.status = 'active'
            attendance.clock_out = None  # Wipes out the accidental checkout time
            attendance.save()
            messages.success(request, f"Successfully restored {target_user.username}'s active shift state.")
        else:
            messages.error(request, f"No attendance log found today for {target_user.username}.")
            
    return redirect('dashboard')

@login_required
def restock_product_view(request, medicine_id):
    # Fetch the product running low
    medicine = get_object_or_404(Medicine, id=medicine_id)
    
    if request.method == 'POST':
        # Get the incoming stock quantity from the form submit payload
        added_quantity = request.POST.get('added_quantity')
        new_cost_price = request.POST.get('cost_price')
        
        if added_quantity and int(added_quantity) > 0:
            # Add new inventory arrival directly to what is currently left on shelves
            medicine.quantity += int(added_quantity)
            
            # Optional: Update cost price if market prices changed for this batch
            if new_cost_price:
                medicine.cost_price = new_cost_price
                
            medicine.save()
            messages.success(request, f"Successfully added {added_quantity} units to {medicine.name} stock.")
            return redirect('dashboard')
        else:
            messages.error(request, "Please enter a valid restock quantity.")
            
    return render(request, 'inventory/restock_product.html', {'medicine': medicine})


