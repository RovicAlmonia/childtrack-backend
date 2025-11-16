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
)
urlpatterns = [
    # Authentication
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),

    # Attendance
    path('attendance/', AttendanceView.as_view(), name='attendance-list'),
    path('attendance/<int:pk>/', AttendanceDetailView.as_view(), name='attendance-detail'),
    path('attendance/public/', PublicAttendanceListView.as_view(), name='public-attendance-list'),

    # Absence
    path('absence/', AbsenceView.as_view(), name='absence-list'),
    path('absence/<int:pk>/', AbsenceDetailView.as_view(), name='absence-detail'),

    # Dropout
    path('dropout/', DropoutView.as_view(), name='dropout-list'),
    path('dropout/<int:pk>/', DropoutDetailView.as_view(), name='dropout-detail'),

    # Unauthorized Person
    path('unauthorized/', UnauthorizedPersonView.as_view(), name='unauthorized-list'),
    path('unauthorized/<int:pk>/', UnauthorizedPersonDetailView.as_view(), name='unauthorized-detail'),

    # SF2 Excel generation
    path('sf2/generate/', generate_sf2_excel, name='generate-sf2-excel'),
]
