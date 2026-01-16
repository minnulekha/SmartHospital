from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
import math

class Department(models.Model):
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name

class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    
    # SMART FEATURE: Tracks average speed (default 15 mins)
    avg_consultation_time = models.IntegerField(default=15)
    
    # STATUS: Is the doctor currently working?
    is_on_duty = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Dr. {self.user.first_name} ({self.department.name})"

    def update_average_time(self, actual_duration_minutes):
        """
        AI ALGORITHM: Recalculates doctor's average speed based on real performance.
        Weighted Average: 70% historical data, 30% most recent patient.
        """
        if actual_duration_minutes < 1: return # Ignore accidental clicks

        # Calculate new weighted average
        new_avg = (self.avg_consultation_time * 0.7) + (actual_duration_minutes * 0.3)
        
        # Enforce limits (Min 5 mins, Max 45 mins) to prevent errors
        new_avg = max(5, min(45, new_avg))
        
        self.avg_consultation_time = math.ceil(new_avg)
        self.save()

class Appointment(models.Model):
    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('in_consultation', 'In Consultation'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    # Basic Info
    patient_name = models.CharField(max_length=100)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='appointments')
    booked_at = models.DateTimeField(auto_now_add=True)
    
    # Unique ID (e.g., 20251020-A1B2)
    ticket_id = models.CharField(max_length=20, unique=True, blank=True)
    token_number = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')

    # Smart Time Tracking Fields
    estimated_start_time = models.DateTimeField(null=True, blank=True) 
    actual_start_time = models.DateTimeField(null=True, blank=True)
    actual_end_time = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        # 1. Generate Unique Ticket ID if missing
        if not self.ticket_id:
            today_str = timezone.now().strftime('%Y%m%d')
            random_code = str(uuid.uuid4())[:4].upper()
            self.ticket_id = f"{today_str}-{random_code}"
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Token {self.token_number} - {self.patient_name}"