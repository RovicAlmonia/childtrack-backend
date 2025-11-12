from django.contrib import admin
from .models import TeacherProfile, Attendance, Absence, Dropout, UnauthorizedPerson

@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'age', 'gender', 'section', 'contact']
    search_fields = ['user__username', 'section', 'contact']
    list_filter = ['gender', 'section']

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'student_lrn', 'teacher', 'date', 'session', 'status', 'timestamp']
    search_fields = ['student_name', 'student_lrn', 'qr_code_data']
    list_filter = ['date', 'status', 'session', 'teacher']
    readonly_fields = ['timestamp']
    ordering = ['-date', '-timestamp']

@admin.register(Absence)
class AbsenceAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'teacher', 'date', 'reason', 'timestamp']
    search_fields = ['student_name', 'reason']
    list_filter = ['date', 'teacher']
    readonly_fields = ['timestamp']

@admin.register(Dropout)
class DropoutAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'teacher', 'date', 'reason', 'timestamp']
    search_fields = ['student_name', 'reason']
    list_filter = ['date', 'teacher']
    readonly_fields = ['timestamp']

@admin.register(UnauthorizedPerson)
class UnauthorizedPersonAdmin(admin.ModelAdmin):
    list_display = ['name', 'student_name', 'guardian_name', 'relation', 'contact', 'timestamp']
    search_fields = ['name', 'student_name', 'guardian_name', 'contact']
    list_filter = ['relation', 'teacher', 'timestamp']
    readonly_fields = ['timestamp']
