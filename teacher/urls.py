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
    generate_half_triangle_excel
)

urlpatterns = [
    # Authentication
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    
    # Attendance
    path('attendance/', AttendanceView.as_view(), name='attendance'),
    path('attendance/<int:pk>/', AttendanceDetailView.as_view(), name='attendance-detail'),
    path('public/attendance/', PublicAttendanceListView.as_view(), name='public_attendance'),
    
    # SF2 Generation
    path('generate-sf2/', generate_sf2_excel, name='generate_sf2'),
    
    # Absences
    path('absences/', AbsenceView.as_view(), name='absences'),
    path('absences/<int:pk>/', AbsenceDetailView.as_view(), name='absence-detail'),
    
    # Dropouts
    path('dropouts/', DropoutView.as_view(), name='dropouts'),
    path('dropouts/<int:pk>/', DropoutDetailView.as_view(), name='dropout-detail'),
    
    # Unauthorized Persons
    path('unauthorized/', UnauthorizedPersonView.as_view(), name='unauthorized'),
    path('unauthorized/<int:pk>/', UnauthorizedPersonDetailView.as_view(), name='unauthorized-detail'),
]

