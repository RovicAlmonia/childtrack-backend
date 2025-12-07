from django.urls import path
from .views import (
    RegistrationView,
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
    ParentGuardianPublicListView,
    ParentLoginView,
    ParentDetailView,
    ParentNotificationListCreateView,
    ParentEventListCreateView,
    ParentEventDetailView,
    ParentScheduleListCreateView,
    AvatarDebugView,
    AvatarRedirectView,  # <-- ADD THIS IMPORT
    AvatarDebugInfoView,  # <-- ADD THIS IMPORT
)

urlpatterns = [
    # Student Registration
    path('register/', AuthenticatedStudentRegistrationView.as_view(), name='authenticated-register'),
    path('public/register/', PublicStudentRegistrationView.as_view(), name='public-register'),
    
    # Teacher & Student Management
    path('teacher-students/', TeacherStudentsView.as_view(), name='teacher-students'),
    path('students/', StudentListView.as_view(), name='student-list'),
    path('students/<str:lrn>/', StudentDetailView.as_view(), name='student-detail'),
    path('all-teachers-students/', AllTeachersStudentsView.as_view(), name='all-teachers-students'),
    
    # Parent/Guardian Management
    path('parents/', ParentGuardianListView.as_view(), name='parent-list'),
    path('parents/public/', ParentGuardianPublicListView.as_view(), name='parent-public-list'),
    path('parent/<int:pk>/', ParentDetailView.as_view(), name='parent-detail'),
    path('by-lrn/<str:lrn>/', ParentsByLRNView.as_view(), name='parents-by-lrn'),
    
    # Parent Login (Web)
    path('login/', ParentLoginView.as_view(), name='parent-login'),
    
    # Parent Mobile App
    path('mobile/register/', ParentMobileRegistrationView.as_view(), name='mobile-register'),
    path('mobile/login/', ParentMobileLoginView.as_view(), name='mobile-login'),
    
    # Notifications
    path('notifications/', ParentNotificationListCreateView.as_view(), name='notification-list-create'),
    
    # Announcements/Events
    path('events/', ParentEventListCreateView.as_view(), name='event-list-create'),
    path('events/<int:pk>/', ParentEventDetailView.as_view(), name='event-detail'),
    
    # Schedules
    path('schedules/', ParentScheduleListCreateView.as_view(), name='schedule-list-create'),
    
    # Avatar endpoints
    path('avatar/<int:pk>/', AvatarRedirectView.as_view(), name='avatar-redirect'),
    path('avatar-debug/<int:pk>/', AvatarDebugInfoView.as_view(), name='avatar-debug-info'),
    path('debug/avatar-exists/', AvatarDebugView.as_view(), name='avatar-debug'),
]