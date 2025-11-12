# urls.py
from django.urls import path
from .views import (
    RegisterView, 
    LoginView, 
    AttendanceView,
    AttendanceDetailView,
    AbsenceView,
    AbsenceDetailView,
    DropoutView,
    DropoutDetailView,
    UnauthorizedPersonView,
    UnauthorizedPersonDetailView,
    PublicAttendanceListView,
    generate_sf2_excel,
    generate_half_triangle_demo
)

urlpatterns = [
    # Authentication endpoints
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    
    # Attendance endpoints
    path('attendance/', AttendanceView.as_view(), name='attendance'),
    path('attendance/<int:pk>/', AttendanceDetailView.as_view(), name='attendance-detail'),
    path('public/attendance/', PublicAttendanceListView.as_view(), name='public_attendance'),
    
    # SF2 Report Generation
    path('generate-sf2/', generate_sf2_excel, name='generate_sf2'),
    path('sf2-demo/', generate_half_triangle_demo, name='sf2_demo'),
    
    # Legacy endpoint (kept for backward compatibility)
    path('api/half-triangle/', generate_half_triangle_demo, name='half_triangle_excel'),
    
    # Absence management endpoints
    path('absences/', AbsenceView.as_view(), name='absences'),
    path('absences/<int:pk>/', AbsenceDetailView.as_view(), name='absence-detail'),
    
    # Dropout management endpoints
    path('dropouts/', DropoutView.as_view(), name='dropouts'),
    path('dropouts/<int:pk>/', DropoutDetailView.as_view(), name='dropout-detail'),
    
    # Unauthorized person tracking endpoints
    path('unauthorized/', UnauthorizedPersonView.as_view(), name='unauthorized'),
    path('unauthorized/<int:pk>/', UnauthorizedPersonDetailView.as_view(), name='unauthorized-detail'),

    # In your api/urls.py, add these lines:
    path('test-sf2/', test_sf2_generation, name='test_sf2'),
    path('generate-simple-sf2/', generate_simple_sf2, name='generate_simple_sf2'),

    
]



