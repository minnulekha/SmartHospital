from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 1. Add Django's built-in auth URLs (Login/Logout)
    path('accounts/', include('django.contrib.auth.urls')),
    
    # 2. Your Hospital App
    path('', include('hospital.urls')), 
]