from django import forms
from .models import Appointment

class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        # ADD 'patient_email' HERE
        fields = ['patient_name', 'patient_email', 'doctor'] 
        widgets = {
            'patient_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Name'}),
            # Add widget for email
            'patient_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter Email'}),
            'doctor': forms.Select(attrs={'class': 'form-control'}),
        }