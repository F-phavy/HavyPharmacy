from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Attendance

# This makes your custom User look like the standard one but with your extra fields
class HavyUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Roles & Status', {'fields': ('role',)}),
    )
    list_display = ['username', 'email', 'role', 'is_staff']

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'status', 'clock_in', 'clock_out')
    list_filter = ('status', 'date')
    search_fields = ('user__username',)    

admin.site.register(User, HavyUserAdmin)
