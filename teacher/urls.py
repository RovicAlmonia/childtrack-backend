# teacher/urls.py
from django.urls import path
from .views import (
    # Authentication
    RegisterView,
    LoginView,

    # Attendance
    AttendanceView,
    attendance_detail,
    PublicAttendanceListView,

    # Absences
    AbsenceView,
    absence_detail,

    # Dropouts
    DropoutView,
    dropout_detail,

    # Unauthorized Persons
    UnauthorizedPersonView,
    unauthorized_person_detail,

    # Reports
    generate_sf2_excel,

     ScanPhotoView,

    MarkUnscannedAbsentView, BulkMarkAbsentView, AbsenceStatsView,
)

urlpatterns = [
    # ========================================
    # AUTHENTICATION ENDPOINTS
    # ========================================
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),

    # ========================================
    # ATTENDANCE ENDPOINTS
    # ========================================
    # List and create attendance records (GET, POST)
    path('attendance/', AttendanceView.as_view(), name='attendance-list'),

    # Retrieve, update, or delete specific attendance record (GET, PUT, PATCH, DELETE)
    path('attendance/<int:pk>/', attendance_detail, name='attendance-detail'),

    # Public attendance list - no authentication required (GET only)
    path('attendance/public/', PublicAttendanceListView.as_view(), name='public-attendance'),

    # ========================================
    # ABSENCE ENDPOINTS
    # ========================================
    # List and create absence records (GET, POST)
    path('absences/', AbsenceView.as_view(), name='absence-list'),

    # Retrieve, update, or delete specific absence record (GET, PUT, PATCH, DELETE)
    path('absences/<int:pk>/', absence_detail, name='absence-detail'),

    # ========================================
    # DROPOUT ENDPOINTS
    # ========================================
    # List and create dropout records (GET, POST)
    path('dropouts/', DropoutView.as_view(), name='dropout-list'),

    # Retrieve, update, or delete specific dropout record (GET, PUT, PATCH, DELETE)
    path('dropouts/<int:pk>/', dropout_detail, name='dropout-detail'),

    # ========================================
    # UNAUTHORIZED PERSON ENDPOINTS
    # ========================================
    # List and create unauthorized person records (GET, POST)
    path('unauthorized/', UnauthorizedPersonView.as_view(), name='unauthorized-list'),

    # Retrieve, update, or delete specific unauthorized person record (GET, PUT, PATCH, DELETE)
    path('unauthorized/<int:pk>/', unauthorized_person_detail, name='unauthorized-detail'),

    # ========================================
    # REPORT GENERATION ENDPOINTS
    # ========================================
    # Generate SF2 Excel report (POST only)
    path('reports/sf2/', generate_sf2_excel, name='generate-sf2'),

    path('scan-photos/', ScanPhotoView.as_view(), name='scan-photos'),

    path('mark-unscanned-absent/', MarkUnscannedAbsentView.as_view(), name='mark-unscanned-absent'),

    path('bulk-mark-absent/', BulkMarkAbsentView.as_view(), name='bulk-mark-absent'),
    
    path('absence-stats/', AbsenceStatsView.as_view(), name='absence-stats'),
]



