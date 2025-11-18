from django.urls import path
from .views import (
    AuthenticatedStudentRegistrationView,
    PublicStudentRegistrationView,
    TeacherStudentsView,
    StudentListView,
    ParentGuardianListView,
    StudentDetailView,
    AllTeachersStudentsView,
    ParentMobileRegistrationView,
    ParentMobileLoginView,
    ParentsByLRNView,
)

urlpatterns = [
    path('register/', AuthenticatedStudentRegistrationView.as_view(), name='register'),
    path('public/register/', PublicStudentRegistrationView.as_view(), name='public-register'),
    path('teacher-students/', TeacherStudentsView.as_view(), name='teacher-students'),
    path('students/', StudentListView.as_view(), name='students-list'),
    path('parents/', ParentGuardianListView.as_view(), name='parents-list'),
    path('students/<str:lrn>/', StudentDetailView.as_view(), name='student-detail'),
    path('all-teachers-students/', AllTeachersStudentsView.as_view(), name='all-teachers-students'),
    
    # Mobile app endpoints
    path('mobile/register/', ParentMobileRegistrationView.as_view(), name='mobile-register'),
    path('mobile/login/', ParentMobileLoginView.as_view(), name='mobile-login'),
    path('by-lrn/<str:lrn>/', ParentsByLRNView.as_view(), name='parents-by-lrn'),
]
