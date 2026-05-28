from django.urls import path
from . import views
# Use local views module directly

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('sales-dashboard/', views.sales_dashboard, name='sales_dashboard'),
    path('attendance/mark/', views.mark_attendance, name='mark_attendance'),
    path('logout/', views.logout_view, name='logout'), 
    path('admin/attendance/reset/<int:user_id>/', views.admin_reset_attendance, name='admin_reset_attendance'),
    path('inventory/add/', views.add_product_view, name='add_product'),
    path('inventory/restock/<int:medicine_id>/', views.restock_product_view, name='restock_product'),
    path('export-shift/', views.export_shift_summary, name='export_shift_summary'),
]