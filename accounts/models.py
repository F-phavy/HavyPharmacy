from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

class User(AbstractUser):
    ADMIN = 'Admin'
    SALESPERSON = 'Salesperson'
    
    ROLE_CHOICES = [
        (ADMIN, 'Admin'),
        (SALESPERSON, 'Salesperson'),
    ]
    
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=SALESPERSON
    )

    # Move this INSIDE the class (indented)
    @property
    def is_admin(self):
        return self.role == self.ADMIN

    def __str__(self):
        return f"{self.username} ({self.role})"

class Attendance(models.Model):
    STATUS_CHOICES = [
        ('inactive', 'Inactive'),
        ('active', 'Active'),
        ('break', 'On Break'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    clock_in = models.DateTimeField(null=True, blank=True)
    clock_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive')
    
    def __str__(self):
        return f"{self.user.username} - {self.date} ({self.status})"