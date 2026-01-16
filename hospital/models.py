from django.db import models
from django.contrib.auth.models import User
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

class Department(models.Model):
    name = models.CharField(max_length=100)
    # Removed location_code as requested
    
    def __str__(self):
        return self.name

class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    avg_consultation_time = models.IntegerField(default=15)
    
    # NEW: Tracks if the doctor is currently in the cabin working
    is_on_duty = models.BooleanField(default=False) 
    
    def __str__(self):
        return f"Dr. {self.user.first_name} ({self.department.name})"


# ... keep your Doctor and Department models same ...

class Appointment(models.Model):
    # Keep your existing fields
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    patient_name = models.CharField(max_length=100)
    # ... other fields ...

    # NEW: Unique Ticket ID (e.g., "20251020-A1B2")
    ticket_id = models.CharField(max_length=20, unique=True, blank=True)
    
    # We still keep token_number for the "Queue Position" (1st, 2nd, 3rd)
    token_number = models.IntegerField(default=0)
    
    status = models.CharField(max_length=20, default='waiting')
    booked_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Generate Unique ID if it doesn't exist
        if not self.ticket_id:
            # Format: YYYYMMDD-XXXX (e.g., 20251020-9F3A)
            today_str = timezone.now().strftime('%Y%m%d')
            random_code = str(uuid.uuid4())[:4].upper()
            self.ticket_id = f"{today_str}-{random_code}"
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.patient_name} - {self.ticket_id}"

# 3. The Queue (Appointments)
class Appointment(models.Model):
    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('in_consultation', 'In Consultation'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    patient_name = models.CharField(max_length=100)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='appointments')
    booked_at = models.DateTimeField(auto_now_add=True)
    
    # The 'Smart' fields
    estimated_start_time = models.DateTimeField(null=True, blank=True) 
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    token_number = models.PositiveIntegerField(null=True, blank=True)
    
    # EXISTING FIELDS
    patient_name = models.CharField(max_length=100)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='appointments')
    booked_at = models.DateTimeField(auto_now_add=True)
    estimated_start_time = models.DateTimeField(null=True, blank=True) 
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    token_number = models.PositiveIntegerField(null=True, blank=True)

    # --- NEW FIELDS FOR AI DATA ---
    actual_start_time = models.DateTimeField(null=True, blank=True)
    actual_end_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Token {self.token_number} - {self.patient_name}"