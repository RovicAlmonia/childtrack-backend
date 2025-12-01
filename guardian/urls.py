
from django.urls import path
from .views import GuardianView, GuardianByTeacherView, GuardianPublicListView, ParentGuardianListView

app_name = 'guardian'

urlpatterns = [
    path('', GuardianView.as_view(), name='guardian-list-create'),
    path('<int:pk>/', GuardianView.as_view(), name='guardian-detail'),
    path('teacher/<int:teacher_id>/', GuardianByTeacherView.as_view(), name='guardian-by-teacher'),
    path('parent/', ParentGuardianListView.as_view(), name='parent-guardian-list'),
    path('parent/<int:pk>/', ParentGuardianListView.as_view(), name='parent-guardian-detail'),
    path('public/', GuardianPublicListView.as_view(), name='guardian-public-list'),
]
