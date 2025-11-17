from django.urls import path
from .views import GuardianView

app_name = 'guardian'

urlpatterns = [
    path('', GuardianView.as_view(), name='guardian-list-create'),
    path('<int:pk>/', GuardianView.as_view(), name='guardian-detail'),
]
