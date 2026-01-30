from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from datetime import timedelta
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
import requests
import json

# Import your models and forms
from .models import Appointment, Doctor, Department
from .forms import AppointmentForm

# ==========================================
# 1. FIREBASE CONFIGURATION (Real-Time)
# ==========================================
# Replace with your actual Firebase URL
FIREBASE_DB_URL = "https://smarthospital-63b2c-default-rtdb.firebaseio.com"

def update_firebase(doctor_id, token_number, status, doctor_name):
    """Sends live updates to Firebase for the mobile app/website"""
    try:
        url = f"{FIREBASE_DB_URL}/doctors/{doctor_id}.json"
        data = {
            "current_token": token_number,
            "status": status,  # 'Live' or 'Offline'
            "doctor_name": doctor_name,
            "last_updated": str(timezone.now())
        }
        requests.patch(url, data=json.dumps(data))
    except Exception as e:
        print(f"⚠️ Firebase Error: {e}")

# ==========================================
# 2. PATIENT & PUBLIC VIEWS
# ==========================================

def home(request):
    """Landing Page"""
    return render(request, 'hospital/home.html')

def get_doctors_ajax(request):
    """Helper for the Check-in Dropdown"""
    department_id = request.GET.get('department_id')
    doctors = Doctor.objects.filter(department_id=department_id, is_on_duty=True).values('id', 'user__first_name', 'user__last_name')
    return JsonResponse({'doctors': list(doctors)})

def patient_check_in(request):
    """Booking Page: Calculates Token Number & Initial ETA"""
    departments = Department.objects.all() 

    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            doctor = appointment.doctor
            
            # Count today's appointments to assign Token Number
            today = timezone.now().date()
            todays_count = Appointment.objects.filter(doctor=doctor, booked_at__date=today).count()
            appointment.token_number = todays_count + 1
            
            # Initial Estimation: Count * Doctor's Average Time
            wait_minutes = todays_count * doctor.avg_consultation_time
            appointment.estimated_start_time = timezone.now() + timedelta(minutes=wait_minutes)
            
            appointment.save()
            return redirect('booking_success', appointment_id=appointment.id)
    else:
        form = AppointmentForm()
    
    return render(request, 'hospital/checkin.html', {'form': form, 'departments': departments})

def booking_success(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    return render(request, 'hospital/success.html', {'appointment': appointment})

def patient_dashboard(request):
    # 1. Get the email from the URL (sent by your Firebase script)
    email = request.GET.get('email')
    history = []
    
    if email:
        # 2. Fetch all appointments matching this email, newest first
        history = Appointment.objects.filter(patient_email=email).order_by('-booked_at')

    # 3. Handle Ticket ID Login (Quick Track)
    if request.method == "POST":
        input_id = request.POST.get('ticket_id').strip() 
        try:
            appointment = Appointment.objects.get(ticket_id=input_id)
            return redirect('patient_live_status', appointment_id=appointment.id)
        except Appointment.DoesNotExist:
            return render(request, 'hospital/patient_dashboard.html', {
                'error': "Invalid Ticket ID.",
                'history': history  # Keep history visible if there's a POST error
            })

    # 4. Pass the history to the template
    return render(request, 'hospital/patient_dashboard.html', {'history': history})

def patient_live_status(request, appointment_id):
    """Smart Tracking Screen for Patients"""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    doctor = appointment.doctor
    
    # Calculate how many people are strictly WAITING ahead of me
    people_ahead = Appointment.objects.filter(
        doctor=doctor, 
        status='waiting', 
        token_number__lt=appointment.token_number
    ).count()
    
    # SMART ESTIMATE: People Ahead * Doctor's Real-Time Speed
    estimated_wait_minutes = people_ahead * doctor.avg_consultation_time
    
    context = {
        'appointment': appointment,
        'doctor': doctor,
        'people_ahead': people_ahead,
        'estimated_wait_minutes': estimated_wait_minutes
    }
    return render(request, 'hospital/patient_live_status.html', context)
def public_display(request):
    """TV Mode for Waiting Room"""
    # Optimized query to get doctor, department, and user data in one go
    active_doctors = Doctor.objects.filter(is_on_duty=True).select_related('department', 'user')
    doctor_data = []
    
    for doc in active_doctors:
        # Get the patient currently in the cabin
        current = Appointment.objects.filter(doctor=doc, status='in_consultation').first()
        
        # Get the next 3 tokens waiting
        waiting = Appointment.objects.filter(doctor=doc, status='waiting').order_by('token_number')[:3]
        
        # We pass the 'doctor' object itself so your template's 
        # {{ item.doctor.user.first_name }} logic will work.
        doctor_data.append({
            'doctor': doc, 
            'dept': doc.department.name,
            'current_token': current.token_number if current else "--",
            'current_name': current.patient_name if current else "Available",
            'waiting': waiting  # Pass the queryset so we can loop in template
        })
        
    return render(request, 'hospital/display.html', {'doctors': doctor_data})

# ==========================================
# 3. DOCTOR & ADMIN VIEWS
# ==========================================

@login_required
def doctor_dashboard(request):
    try:
        # Access the doctor profile linked to the logged-in user
        doctor = request.user.doctor 
    except Exception:
        return render(request, 'hospital/error.html', {'message': "Access Denied. Doctor profile not found."})

    # 1. Get the patient currently in the cabin
    current_patient = Appointment.objects.filter(
        doctor=doctor, 
        status='in_consultation'
    ).first()

    # 2. Get the list of patients waiting (The Queue)
    queue = Appointment.objects.filter(
        doctor=doctor, 
        status='waiting'
    ).order_by('token_number')

    # 3. NEW: Get today's completed appointments (The History)
    # This allows the doctor to see a list of patients they have already finished
    today = timezone.now().date()
    history = Appointment.objects.filter(
        doctor=doctor, 
        status='completed',
        booked_at__date=today
    ).order_by('-actual_end_time') # Show most recently finished first

    return render(request, 'hospital/dashboard.html', {
        'queue': queue, 
        'doctor': doctor,
        'current_patient': current_patient,
        'history': history, # Pass the history to the template
    })

@login_required
def call_patient(request, appointment_id):
    """Doctor clicks 'Next Patient'"""
    doctor = request.user.doctor
    
    # 1. FINISH PREVIOUS PATIENT (And Calculate Speed)
    current_patient = Appointment.objects.filter(doctor=doctor, status='in_consultation').first()
    if current_patient:
        current_patient.status = 'completed'
        current_patient.actual_end_time = timezone.now()
        current_patient.save()
        
        # --- AI TIME UPDATE ---
        duration = current_patient.actual_end_time - current_patient.actual_start_time
        duration_minutes = duration.total_seconds() / 60
        doctor.update_average_time(duration_minutes)

    # 2. START NEW PATIENT
    new_patient = get_object_or_404(Appointment, id=appointment_id)
    new_patient.status = 'in_consultation'
    new_patient.actual_start_time = timezone.now()
    new_patient.save()
    
    # 3. SYNC FIREBASE
    update_firebase(doctor.id, new_patient.token_number, "Live", doctor.user.first_name)
    
    return redirect('doctor_dashboard')

from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from datetime import timedelta
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
import requests
import json

# Import your models and forms
from .models import Appointment, Doctor, Department
from .forms import AppointmentForm

# ==========================================
# 1. FIREBASE CONFIGURATION (Real-Time)
# ==========================================
FIREBASE_DB_URL = "https://smarthospital-63b2c-default-rtdb.firebaseio.com"

def update_firebase(doctor_id, token_number, status, doctor_name):
    """Sends live updates to Firebase for the mobile app/website"""
    try:
        url = f"{FIREBASE_DB_URL}/doctors/{doctor_id}.json"
        data = {
            "current_token": token_number,
            "status": status,
            "doctor_name": doctor_name,
            "last_updated": str(timezone.now())
        }
        requests.patch(url, data=json.dumps(data))
    except Exception as e:
        print(f"⚠️ Firebase Error: {e}")

# ==========================================
# 2. PATIENT & PUBLIC VIEWS
# ==========================================

def home(request):
    return render(request, 'hospital/home.html')

def get_doctors_ajax(request):
    department_id = request.GET.get('department_id')
    doctors = Doctor.objects.filter(department_id=department_id, is_on_duty=True).values('id', 'user__first_name', 'user__last_name')
    return JsonResponse({'doctors': list(doctors)})

def patient_check_in(request):
    """Booking Page: Captures Email for History Tracking"""
    departments = Department.objects.all() 

    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            doctor = appointment.doctor
            
            # Count today's appointments for Token Number
            today = timezone.now().date()
            todays_count = Appointment.objects.filter(doctor=doctor, booked_at__date=today).count()
            appointment.token_number = todays_count + 1
            
            # Capture email from the form/POST data for history
            appointment.patient_email = request.POST.get('patient_email') 
            
            # Initial Estimation
            wait_minutes = todays_count * doctor.avg_consultation_time
            appointment.estimated_start_time = timezone.now() + timedelta(minutes=wait_minutes)
            
            appointment.save()
            return redirect('booking_success', appointment_id=appointment.id)
    else:
        form = AppointmentForm()
    
    return render(request, 'hospital/checkin.html', {'form': form, 'departments': departments})

def booking_success(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    return render(request, 'hospital/success.html', {'appointment': appointment})

def patient_dashboard(request):
    """Handles History via Email and Quick Track via Ticket ID"""
    email = request.GET.get('email')
    history = []
    
    if email:
        history = Appointment.objects.filter(patient_email=email).order_by('-booked_at')

    if request.method == "POST":
        input_id = request.POST.get('ticket_id').strip() 
        try:
            appointment = Appointment.objects.get(ticket_id=input_id)
            return redirect('patient_live_status', appointment_id=appointment.id)
        except Appointment.DoesNotExist:
            return render(request, 'hospital/patient_dashboard.html', {
                'error': "Invalid Ticket ID.",
                'history': history
            })

    return render(request, 'hospital/patient_dashboard.html', {'history': history})

def patient_live_status(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    doctor = appointment.doctor
    
    people_ahead = Appointment.objects.filter(
        doctor=doctor, 
        status='waiting', 
        token_number__lt=appointment.token_number
    ).count()
    
    estimated_wait_minutes = people_ahead * doctor.avg_consultation_time
    
    context = {
        'appointment': appointment,
        'doctor': doctor,
        'people_ahead': people_ahead,
        'estimated_wait_minutes': estimated_wait_minutes
    }
    return render(request, 'hospital/patient_live_status.html', context)

def public_display(request):
    active_doctors = Doctor.objects.filter(is_on_duty=True).select_related('department', 'user')
    doctor_data = []
    
    for doc in active_doctors:
        current = Appointment.objects.filter(doctor=doc, status='in_consultation').first()
        waiting = Appointment.objects.filter(doctor=doc, status='waiting').order_by('token_number')[:3]
        
        doctor_data.append({
            'doctor': doc, 
            'dept': doc.department.name,
            'current_token': current.token_number if current else "--",
            'current_name': current.patient_name if current else "Available",
            'waiting': waiting 
        })
        
    return render(request, 'hospital/display.html', {'doctors': doctor_data})

# ==========================================
# 3. DOCTOR & ADMIN VIEWS (Fixed TypeErrors)
# ==========================================

@login_required
def doctor_dashboard(request):
    try:
        doctor = request.user.doctor 
    except Exception:
        return render(request, 'hospital/error.html', {'message': "Access Denied."})

    current_patient = Appointment.objects.filter(doctor=doctor, status='in_consultation').first()
    queue = Appointment.objects.filter(doctor=doctor, status='waiting').order_by('token_number')
    
    today = timezone.now().date()
    history = Appointment.objects.filter(
        doctor=doctor, 
        status='completed',
        booked_at__date=today
    ).order_by('-actual_end_time')

    return render(request, 'hospital/dashboard.html', {
        'queue': queue, 
        'doctor': doctor,
        'current_patient': current_patient,
        'history': history,
    })

@login_required
def call_patient(request, appointment_id):
    """Doctor clicks 'Next Patient' - Handles calculation safety"""
    doctor = request.user.doctor
    
    # 1. FINISH PREVIOUS PATIENT
    current_patient = Appointment.objects.filter(doctor=doctor, status='in_consultation').first()
    if current_patient:
        current_patient.status = 'completed'
        current_patient.actual_end_time = timezone.now()
        
        # Safety Check: Only calculate if start time exists to avoid TypeError
        if current_patient.actual_start_time:
            duration = current_patient.actual_end_time - current_patient.actual_start_time
            duration_minutes = duration.total_seconds() / 60
            doctor.update_average_time(duration_minutes)
        
        current_patient.save()

    # 2. START NEW PATIENT
    new_patient = get_object_or_404(Appointment, id=appointment_id)
    new_patient.status = 'in_consultation'
    new_patient.actual_start_time = timezone.now()
    new_patient.save()
    
    # 3. SYNC FIREBASE
    update_firebase(doctor.id, new_patient.token_number, "Live", doctor.user.first_name)
    
    return redirect('doctor_dashboard')

@login_required
def complete_appointment(request, appointment_id):
    """Doctor clicks 'Finish' - Fixed NoneType subtraction error"""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    appointment.status = 'completed'
    appointment.actual_end_time = timezone.now()
    
    # FIX: Check for actual_start_time before subtraction
    if appointment.actual_start_time:
        duration = appointment.actual_end_time - appointment.actual_start_time
        duration_minutes = duration.total_seconds() / 60
        appointment.doctor.update_average_time(duration_minutes)
    else:
        # Fallback: if start time is missing, set it to end time so history stays valid
        appointment.actual_start_time = appointment.actual_end_time
    
    appointment.save()
    
    # Reset Firebase to 0 (Available)
    update_firebase(appointment.doctor.id, 0, "Live", appointment.doctor.user.first_name)
    
    return redirect('doctor_dashboard')

@login_required
def toggle_duty(request):
    try:
        doctor = request.user.doctor
        doctor.is_on_duty = not doctor.is_on_duty
        doctor.save()
        status = "Live" if doctor.is_on_duty else "Offline"
        update_firebase(doctor.id, 0, status, doctor.user.first_name)
    except:
        pass
    return redirect('doctor_dashboard')

# ==========================================
# 4. UTILITIES
# ==========================================

def download_pdf(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    template_path = 'hospital/pdf_token.html'
    context = {'appointment': appointment}
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Token_{appointment.token_number}.pdf"'
    
    template = get_template(template_path)
    html = template.render(context)
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response

@login_required
def toggle_duty(request):
    """Go Online / Offline"""
    try:
        doctor = request.user.doctor
        doctor.is_on_duty = not doctor.is_on_duty
        doctor.save()
        status = "Live" if doctor.is_on_duty else "Offline"
        update_firebase(doctor.id, 0, status, doctor.user.first_name)
    except:
        pass
    return redirect('doctor_dashboard')

# ==========================================
# 4. UTILITIES
# ==========================================

def download_pdf(request, appointment_id):
    """Generates PDF Token"""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    template_path = 'hospital/pdf_token.html'
    context = {'appointment': appointment}
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Token_{appointment.token_number}.pdf"'
    
    template = get_template(template_path)
    html = template.render(context)
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response