from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    AttendanceView,
    AttendanceDetailView,
    UnauthorizedPersonView,
    UnauthorizedPersonDetailView,
    PublicAttendanceListView,
    generate_sf2_excel,
    bulk_update_attendance,
)

app_name = 'attendance'

urlpatterns = [
    # Authentication endpoints
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    
    # Attendance endpoints
    path('attendance/', AttendanceView.as_view(), name='attendance-list'),
    path('attendance/<int:pk>/', AttendanceDetailView.as_view(), name='attendance-detail'),
    path('attendance/bulk-update/', bulk_update_attendance, name='bulk-update-attendance'),
    path('attendance/public/', PublicAttendanceListView.as_view(), name='public-attendance-list'),
    
    # Unauthorized person endpoints
    path('unauthorized/', UnauthorizedPersonView.as_view(), name='unauthorized-list'),
    path('unauthorized/<int:pk>/', UnauthorizedPersonDetailView.as_view(), name='unauthorized-detail'),
    
    # SF2 Excel generation endpoint
    path('sf2/generate/', generate_sf2_excel, name='generate-sf2-excel'),
]
