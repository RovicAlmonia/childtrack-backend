from django.urls import path
from .views import GuardianView, GuardianByTeacherView, GuardianPublicListView

app_name = 'guardian'

urlpatterns = [
    path('', GuardianView.as_view(), name='guardian-list-create'),
    path('<int:pk>/', GuardianView.as_view(), name='guardian-detail'),
    path('teacher/<int:teacher_id>/', GuardianByTeacherView.as_view(), name='guardian-by-teacher'),
     # new
    path('public/', GuardianPublicListView.as_view(), name='guardian-public-list'),

]
