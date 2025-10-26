from django.contrib import admin
from .models import TeacherProfile, Attendance

@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'age', 'gender', 'section', 'contact']
    search_fields = ['user__username', 'section', 'contact']
    list_filter = ['gender', 'section']

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'teacher', 'timestamp']
    search_fields = ['student_name', 'qr_code_data']
    list_filter = ['timestamp', 'teacher']
    readonly_fields = ['timestamp']
