from django.contrib import admin
from .models import Department, Doctor, Appointment

admin.site.register(Department)
admin.site.register(Doctor)

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('token_number', 'patient_name', 'doctor', 'status', 'estimated_start_time')
    list_filter = ('status', 'doctor')