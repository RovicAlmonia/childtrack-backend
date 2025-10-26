from django.urls import path
from .views import (
    RegisterView, 
    LoginView, 
    AttendanceView, 
    PublicAttendanceListView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('attendance/', AttendanceView.as_view(), name='attendance'),
    path('public/attendance/', PublicAttendanceListView.as_view(), name='public_attendance'),
]
