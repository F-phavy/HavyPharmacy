from django.contrib import admin
from django.urls import path, include
from accounts import views  # <--- YOU NEED THIS IMPORT

urlpatterns = [
    # 1. Root path for your landing page
    path('', views.landing_page, name='home'),
    
    # 2. Your custom app paths
    path('', include('accounts.urls')),
    
    # 3. Built-in Django Admin
    path('admin/', admin.site.urls),
    
    # 4. Sales app routes
    path('', include('sales.urls')),
    
    # 5. Django Auth
    path('accounts/', include('django.contrib.auth.urls')),
]