from django.urls import path
from . import views

urlpatterns = [
    # Add your sales-specific routes here
    # Example:
    # path('pos/', views.pos_view, name='pos_view'),
    path('pos/', views.pos_view, name='pos_view'),
    path('receipt/<int:sale_id>/', views.receipt_view, name='receipt_view'),
    path('stock/', views.stock_list, name='stock_list'),
]