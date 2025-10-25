from django.urls import path
from .views import GuardianView

urlpatterns = [
    path('', GuardianView.as_view(), name='guardian'),
]
