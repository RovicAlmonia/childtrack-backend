from django.urls import path
from .views import (
    AuthenticatedStudentRegistrationView,
    PublicStudentRegistrationView,
    TeacherStudentsView,
    StudentListView,
    ParentGuardianListView,
    StudentDetailView,
    AllTeachersStudentsView,
)

urlpatterns = [
    path('register/', AuthenticatedStudentRegistrationView.as_view(), name='register'),
    path('public/register/', PublicStudentRegistrationView.as_view(), name='public-register'),
    path('teacher-students/', TeacherStudentsView.as_view(), name='teacher-students'),
    path('students/', StudentListView.as_view(), name='students-list'),
    path('parents/', ParentGuardianListView.as_view(), name='parents-list'),
    path('students/<str:lrn>/', StudentDetailView.as_view(), name='student-detail'),
    path('all-teachers-students/', AllTeachersStudentsView.as_view(), name='all-teachers-students'),
]
