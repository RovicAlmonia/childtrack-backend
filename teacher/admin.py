from django.contrib import admin
from .models import TeacherProfile, Attendance, UnauthorizedPerson, ScanPhoto

@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'section', 'age', 'gender', 'contact']
    search_fields = ['user__username', 'section']
    list_filter = ['gender', 'section']

@admin.register(ScanPhoto)
class ScanPhotoAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'status', 'teacher', 'timestamp']
    search_fields = ['student_name', 'teacher__user__username']
    list_filter = ['status', 'timestamp']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'guardian_name', 'teacher', 'date', 'status', 'transaction_type', 'session', 'gender', 'timestamp']
    search_fields = ['student_name', 'student_lrn', 'guardian_name', 'teacher__user__username']
    list_filter = ['status', 'transaction_type', 'date', 'session', 'gender', 'teacher']
    date_hierarchy = 'date'
    ordering = ['-date', '-timestamp']

"""
@admin.register(UnauthorizedPerson)
class UnauthorizedPersonAdmin(admin.ModelAdmin):
    list_display = ['name', 'student_name', 'guardian_name', 'relation', 'contact', 'timestamp']
    search_fields = ['name', 'student_name', 'guardian_name', 'contact']
    list_filter = ['relation', 'timestamp']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
"""
