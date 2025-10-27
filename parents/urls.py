from django.urls import path
from .views import (
    StudentRegistrationView,
    StudentListView,
    ParentGuardianListView,
    StudentDetailView
)

urlpatterns = [
    path('register/', StudentRegistrationView.as_view(), name='student_register'),
    path('students/', StudentListView.as_view(), name='student_list'),
    path('students/<str:lrn>/', StudentDetailView.as_view(), name='student_detail'),
    path('parents/', ParentGuardianListView.as_view(), name='parent_list'),
    path('parents/<str:lrn>/', ParentGuardianListView.as_view(), name='parent_by_student'),
]
