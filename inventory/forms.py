# inventory/forms.py
from django import forms
from .models import Medicine  # Make sure your model name matches this

class MedicineForm(forms.ModelForm):
    class Meta:
        model = Medicine
        fields = '__all__'  # Or list specific fields like ['name', 'price', 'quantity']