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

# In development `static()` is only added when DEBUG is True. On some deployments
# (like Render) media files may still be stored on the instance filesystem and
# need to be served while you move to a proper production storage solution.
# Add MEDIA serving unconditionally as a temporary measure so uploaded avatars
# under `/media/` are reachable. Replace with Cloudinary/S3-backed storage
# for a production-safe solution.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
