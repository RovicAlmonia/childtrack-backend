from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from parents.views import ParentNotificationListCreateView, ParentEventListCreateView, ParentScheduleListCreateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('teacher.urls')),
    path('api/guardian/', include('guardian.urls')),
    path('api/parents/', include('parents.urls')),  # ✅ ADD THIS
    path('api/notifications/', ParentNotificationListCreateView.as_view(), name='notifications'),
    path('api/events/', ParentEventListCreateView.as_view(), name='events'),
    path('api/schedule/', ParentScheduleListCreateView.as_view(), name='schedule'),
]

# from django.urls import path
# from .views import GuardianView, GuardianByTeacherView, GuardianPublicListView, ParentGuardianListView

# app_name = 'guardian'

# urlpatterns = [
#     path('', GuardianView.as_view(), name='guardian-list-create'),
#     path('<int:pk>/', GuardianView.as_view(), name='guardian-detail'),
#     path('teacher/<int:teacher_id>/', GuardianByTeacherView.as_view(), name='guardian-by-teacher'),
#     path('parent/', ParentGuardianListView.as_view(), name='parent-guardian-list'),
#     path('parent/<int:pk>/', ParentGuardianListView.as_view(), name='parent-guardian-detail'),
#     path('public/', GuardianPublicListView.as_view(), name='guardian-public-list'),
# ]
