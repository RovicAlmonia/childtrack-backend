from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.TeacherRegisterView.as_view(), name='teacher-register'),
    path('login/', views.TeacherLoginView.as_view(), name='teacher-login'),
]
