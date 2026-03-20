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

def get_last_token_from_firebase(doctor_id):
    """Fetches the absolute last issued token from Firebase, handling missing or messy data."""
    try:
        url = f"{FIREBASE_DB_URL}/doctors/{doctor_id}/last_issued_token.json"
        response = requests.get(url, timeout=5)
        token_data = response.json()
        
        # Debugging print - look at your terminal when you book a token!
        print(f"DEBUG Firebase Fetch: Doctor {doctor_id} returned: {token_data} (Type: {type(token_data)})")

        if token_data is None:
            return 0
            
        # If it comes back as a dictionary (e.g., if you accidentally nested it in Firebase)
        if isinstance(token_data, dict):
            print("⚠️ WARNING: Firebase returned a dictionary, not a number. Resetting to 0.")
            return 0
            
        # Convert to int, strip quotes if it's a string
        return int(str(token_data).strip('"\''))
        
    except Exception as e:
        print(f"⚠️ Firebase Fetch Error: {e}")
        return 0

def update_firebase(doctor_id, current_serving, status, doctor_name, update_last_issued=None):
    """
    Sends live updates. 
    If update_last_issued is a number, it updates the 'high water mark' counter.
    """
    try:
        url = f"{FIREBASE_DB_URL}/doctors/{doctor_id}.json"
        
        # Base data for the doctor's live card
        data = {
            "status": status,
            "doctor_name": doctor_name,
            "last_updated": str(timezone.now())
        }
        
        # Only update current_token if a doctor is calling a patient
        if current_serving > 0:
            data["current_token"] = current_serving
            
        # Update the counter ONLY if we are booking (pass the new token number here)
        if update_last_issued is not None:
            data["last_issued_token"] = update_last_issued

        requests.patch(url, data=json.dumps(data), timeout=5)
    except Exception as e:
        print(f"⚠️ Firebase Sync Error: {e}")

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
    departments = Department.objects.all() 

    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            doctor = appointment.doctor
            
            # 1. Get last token from Firebase
            last_token_fb = get_last_token_from_firebase(doctor.id)
            
            # 2. Safety Check: If server hasn't reset, local count might be higher
            today = timezone.now().date()
            local_count = Appointment.objects.filter(doctor=doctor, booked_at__date=today).count()
            
            # 3. Calculate new token (The Max ensures we never duplicate)
            new_token = max(last_token_fb, local_count) + 1
            appointment.token_number = new_token
            
            # 4. SYNC TO FIREBASE: Pass new_token to update_last_issued
            update_firebase(doctor.id, 0, "Live", doctor.user.first_name, update_last_issued=new_token)
            
            appointment.patient_email = request.POST.get('patient_email') 
            
            # Initial Estimation
            wait_minutes = (new_token - 1) * doctor.avg_consultation_time
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
    
    # local counting for "people ahead" is okay for current session
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
# 3. DOCTOR & ADMIN VIEWS
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
    doctor = request.user.doctor
    
    # 1. FINISH PREVIOUS PATIENT
    current_patient = Appointment.objects.filter(doctor=doctor, status='in_consultation').first()
    if current_patient:
        current_patient.status = 'completed'
        current_patient.actual_end_time = timezone.now()
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
    appointment = get_object_or_404(Appointment, id=appointment_id)
    appointment.status = 'completed'
    appointment.actual_end_time = timezone.now()
    
    if appointment.actual_start_time:
        duration = appointment.actual_end_time - appointment.actual_start_time
        duration_minutes = duration.total_seconds() / 60
        appointment.doctor.update_average_time(duration_minutes)
    else:
        appointment.actual_start_time = appointment.actual_end_time
    
    appointment.save()
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