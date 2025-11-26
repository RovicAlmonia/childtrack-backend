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

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
