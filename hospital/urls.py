from django.urls import path
from . import views

urlpatterns = [
    # 1. Public Pages
    path('', views.home, name='home'),
    path('book/', views.patient_check_in, name='patient_check_in'),
    path('success/<int:appointment_id>/', views.booking_success, name='booking_success'),
    
    # 2. PATIENT DASHBOARD (Login & Menu)
    path('patient-dashboard/', views.patient_dashboard, name='patient_dashboard'),
    
    # 3. LIVE STATUS (The Timer & Map)
    path('live-status/<int:appointment_id>/', views.patient_live_status, name='patient_live_status'),

    # 4. Doctor Dashboard & Actions
    path('dashboard/', views.doctor_dashboard, name='doctor_dashboard'),
    path('call/<int:appointment_id>/', views.call_patient, name='call_patient'),
    path('complete/<int:appointment_id>/', views.complete_appointment, name='complete_appointment'),
    path('toggle-duty/', views.toggle_duty, name='toggle_duty'),

    # 5. Utilities
    path('get-doctors/', views.get_doctors_ajax, name='get_doctors'),
    path('pdf/<int:appointment_id>/', views.download_pdf, name='download_pdf'),
    path('display/', views.public_display, name='public_display'),
]