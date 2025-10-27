from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('teacher.urls')),
    path('api/guardian/', include('guardian.urls')),
    path('api/parents/', include('parents.urls')),  # ✅ ADD THIS
]
