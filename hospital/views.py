from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from datetime import timedelta
from django.db.models import Avg
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
import requests
import json

# Import your models and form
from .models import Appointment, Doctor, Department
from .forms import AppointmentForm

# ==========================================
# 1. GOOGLE FIREBASE SETUP (Real-Time)
# ==========================================
# 🔴 IMPORTANT: Replace this with your actual Firebase Database URL
FIREBASE_DB_URL = "https://smarthospital-63b2c-default-rtdb.firebaseio.com"

def update_firebase(doctor_id, token_number, status):
    """
    Sends data to Firebase so patients see it INSTANTLY.
    """
    try:
        url = f"{FIREBASE_DB_URL}/doctors/{doctor_id}.json"
        data = {
            "current_token": token_number,
            "status": status, # 'Live' or 'Offline'
            "last_updated": str(timezone.now())
        }
        requests.patch(url, data=json.dumps(data))
    except Exception as e:
        print(f"⚠️ Firebase Error: {e}")

# ==========================================
# 2. AJAX & AI HELPER FUNCTIONS
# ==========================================

def get_doctors(request):
    department_id = request.GET.get('department_id')
    doctors = Doctor.objects.filter(department_id=department_id, is_on_duty=True).values('id', 'user__first_name', 'user__last_name')
    return list(doctors)

def get_doctors_ajax(request):
    doctors = get_doctors(request)
    return JsonResponse({'doctors': doctors})

def update_doctor_avg_time(doctor):
    """AI LOGIC: Learns doctor speed based on last 10 patients."""
    recent_apps = Appointment.objects.filter(
        doctor=doctor, 
        status='completed',
        actual_start_time__isnull=False,
        actual_end_time__isnull=False
    ).order_by('-actual_end_time')[:10]

    if recent_apps.count() > 0:
        total_duration = 0
        for app in recent_apps:
            duration = (app.actual_end_time - app.actual_start_time).total_seconds() / 60
            total_duration += duration
        
        new_avg = int(total_duration / recent_apps.count())
        if new_avg < 5: new_avg = 5
        
        doctor.avg_consultation_time = new_avg
        doctor.save()

# ==========================================
# 3. PUBLIC SIDE & PATIENT PORTAL
# ==========================================

def home(request):
    return render(request, 'hospital/home.html')

def patient_check_in(request):
    departments = Department.objects.all() 

    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            doctor = appointment.doctor
            
            # --- CRITICAL FIX START ---
            # We count ALL appointments booked today (even completed ones).
            # This ensures the token number never repeats or goes backward.
            today = timezone.now().date()
            todays_apps_count = Appointment.objects.filter(
                doctor=doctor, 
                booked_at__date=today
            ).count()
            
            appointment.token_number = todays_apps_count + 1
            # --- CRITICAL FIX END ---

            # Smart ETA Calculation
            wait_minutes = todays_apps_count * doctor.avg_consultation_time
            appointment.estimated_start_time = timezone.now() + timedelta(minutes=wait_minutes)
            
            appointment.save()
            return redirect('booking_success', appointment_id=appointment.id)
    else:
        form = AppointmentForm()
    
    return render(request, 'hospital/checkin.html', {'form': form, 'departments': departments})

def booking_success(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    return render(request, 'hospital/success.html', {'appointment': appointment})

# --- REORGANIZED PATIENT VIEWS ---

def patient_dashboard(request):
    """
    Main Menu: Users enter their UNIQUE TICKET ID (e.g. 20251020-A1B2)
    """
    if request.method == "POST":
        # Get the input string
        input_id = request.POST.get('ticket_id').strip() 
        
        try:
            # Search by the new Unique ID field
            appointment = Appointment.objects.get(ticket_id=input_id)
            return redirect('patient_live_status', appointment_id=appointment.id)
            
        except Appointment.DoesNotExist:
            return render(request, 'hospital/patient_dashboard.html', {
                'error': "Invalid Ticket ID. Please check your PDF."
            })

    return render(request, 'hospital/patient_dashboard.html')

def patient_live_status(request, appointment_id):
    """
    The Specific Timer & Map Screen.
    """
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    context = {
        'appointment': appointment,
        'doctor_id': appointment.doctor.id,
        'my_token': appointment.token_number,
        'avg_time': appointment.doctor.avg_consultation_time,
        'doctor_name': appointment.doctor.user.last_name,
        'department': appointment.doctor.department.name
    }
    return render(request, 'hospital/patient_live_status.html', context)

# ==========================================
# 4. UTILITIES
# ==========================================

def public_display(request):
    """
    Shows a big TV-style dashboard for the waiting room.
    Displays ALL doctors currently marked as 'is_on_duty'.
    """
    # Get all doctors who are currently working
    active_doctors = Doctor.objects.filter(is_on_duty=True).select_related('department', 'user')
    
    doctor_data = []
    
    for doc in active_doctors:
        # Get current patient (if any)
        current = Appointment.objects.filter(doctor=doc, status='in_consultation').first()
        
        # Get next 3 people waiting
        waiting_list = Appointment.objects.filter(doctor=doc, status='waiting').order_by('token_number')[:3]
        
        doctor_data.append({
            'doctor': doc,
            'dept': doc.department.name,
            'current_token': current.token_number if current else "--",
            'current_name': current.patient_name if current else "Available",
            'waiting': waiting_list
        })
        
    return render(request, 'hospital/display.html', {'doctors': doctor_data})

def download_pdf(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    template_path = 'hospital/pdf_token.html'
    context = {'appointment': appointment}
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Token_{appointment.token_number}.pdf"'
    template = get_template(template_path)
    html = template.render(context)
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err: return HttpResponse('Errors')
    return response

# ==========================================
# 5. DOCTOR SIDE
# ==========================================

@login_required
def doctor_dashboard(request):
    try:
        doctor = request.user.doctor
    except:
        return render(request, 'hospital/error.html', {'message': "Access Denied: You are not a registered Doctor."})

    current_patient = Appointment.objects.filter(doctor=doctor, status='in_consultation').first()
    queue = Appointment.objects.filter(doctor=doctor, status='waiting').order_by('token_number')
    
    return render(request, 'hospital/dashboard.html', {
        'queue': queue, 
        'doctor': doctor,
        'current_patient': current_patient
    })

@login_required
def call_patient(request, appointment_id):
    doctor = request.user.doctor
    
    # 1. Finish Previous
    current_patient = Appointment.objects.filter(doctor=doctor, status='in_consultation').first()
    if current_patient:
        current_patient.status = 'completed'
        current_patient.actual_end_time = timezone.now() 
        current_patient.save()
        update_doctor_avg_time(doctor)

    # 2. Call New
    new_patient = get_object_or_404(Appointment, id=appointment_id)
    new_patient.status = 'in_consultation'
    new_patient.actual_start_time = timezone.now()
    new_patient.save()
    
    # 3. SYNC WITH GOOGLE FIREBASE
    update_firebase(doctor.id, new_patient.token_number, "Live")
    
    return redirect('doctor_dashboard')

@login_required
def complete_appointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    appointment.status = 'completed'
    appointment.actual_end_time = timezone.now()
    appointment.save()
    
    update_firebase(appointment.doctor.id, 0, "Live")
    update_doctor_avg_time(appointment.doctor)
    return redirect('doctor_dashboard')

@login_required
def toggle_duty(request):
    try:
        doctor = request.user.doctor
        doctor.is_on_duty = not doctor.is_on_duty
        doctor.save()
        status = "Live" if doctor.is_on_duty else "Offline"
        update_firebase(doctor.id, 0, status)
    except:
        pass
    return redirect('doctor_dashboard')