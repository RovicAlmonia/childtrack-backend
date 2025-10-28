from django.urls import path
from .views import (
    StudentRegistrationView,
    PublicStudentRegistrationView,
    MyStudentsView,
    MyParentsGuardiansView,
    TeacherDashboardStatsView,
    StudentDetailView
)

urlpatterns = [
    # Teacher-authenticated endpoints
    path('register/', StudentRegistrationView.as_view(), name='student_register'),
    path('my-students/', MyStudentsView.as_view(), name='my_students'),
    path('my-parents/', MyParentsGuardiansView.as_view(), name='my_parents'),
    path('dashboard-stats/', TeacherDashboardStatsView.as_view(), name='dashboard_stats'),
    path('students/<str:lrn>/', StudentDetailView.as_view(), name='student_detail'),
    
    # Public endpoint for parent/guardian self-registration
    path('public/register/', PublicStudentRegistrationView.as_view(), name='public_register'),
]
