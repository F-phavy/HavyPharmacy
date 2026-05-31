from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User

class HavySignUpForm(UserCreationForm):
    # This is the "Secret Gate" field
    admin_key = forms.CharField(
        required=False, 
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter Admin Key if choosing Admin role'}),
        help_text="Only required for Admin registration."
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "role")

    def save(self, commit=True):
        user = super().save(commit=False)
        # Verify the secret key
        entered_key = self.cleaned_data.get('admin_key')
        
        if user.role == 'Admin' and entered_key == "HAVY2026":
            user.is_staff = True      # REQUIRED for Admin Panel access
            user.is_superuser = True  # Full permissions
        else:
            user.role = 'Salesperson'
            user.is_staff = False
            
        if commit:
            user.save()
        return user    