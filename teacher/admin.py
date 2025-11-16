from django.contrib import admin
from .models import TeacherProfile, Attendance, UnauthorizedPerson

@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'section', 'age', 'gender', 'contact']
    search_fields = ['user__username', 'section']
    list_filter = ['gender', 'section']

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'teacher', 'date', 'status', 'session', 'gender', 'timestamp']
    search_fields = ['student_name', 'student_lrn', 'teacher__user__username']
    list_filter = ['status', 'date', 'session', 'gender', 'teacher']
    date_hierarchy = 'date'
    ordering = ['-date', '-timestamp']

@admin.register(UnauthorizedPerson)
class UnauthorizedPersonAdmin(admin.ModelAdmin):
    list_display = ['name', 'student_name', 'guardian_name', 'relation', 'contact', 'timestamp']
    search_fields = ['name', 'student_name', 'guardian_name', 'contact']
    list_filter = ['relation', 'timestamp']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
