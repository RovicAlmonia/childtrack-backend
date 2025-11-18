from django.contrib import admin
from .models import TeacherProfile, Guardian, Attendance, Absence, Dropout, UnauthorizedPerson


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'section', 'age', 'gender', 'contact']
    search_fields = ['user__username', 'section']
    list_filter = ['gender', 'section']


@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    list_display = ['guardian_name', 'student_name', 'relation', 'contact', 'is_primary', 'teacher', 'timestamp']
    search_fields = ['guardian_name', 'student_name', 'student_lrn', 'contact', 'teacher__user__username']
    list_filter = ['relation', 'is_primary', 'teacher']
    date_hierarchy = 'timestamp'
    ordering = ['-is_primary', 'student_name', 'guardian_name']
    fieldsets = (
        ('Student Information', {
            'fields': ('teacher', 'student_name', 'student_lrn')
        }),
        ('Guardian Information', {
            'fields': ('guardian_name', 'relation', 'contact', 'email', 'address', 'occupation')
        }),
        ('Emergency & Additional', {
            'fields': ('emergency_contact', 'photo', 'is_primary')
        }),
    )


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'teacher', 'date', 'status', 'session', 'gender', 'timestamp']
    search_fields = ['student_name', 'student_lrn', 'teacher__user__username']
    list_filter = ['status', 'date', 'session', 'gender', 'teacher']
    date_hierarchy = 'date'
    ordering = ['-date', '-timestamp']


@admin.register(Absence)
class AbsenceAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'teacher', 'date', 'reason', 'timestamp']
    search_fields = ['student_name', 'teacher__user__username']
    list_filter = ['date', 'teacher']
    date_hierarchy = 'date'
    ordering = ['-date', '-timestamp']


@admin.register(Dropout)
class DropoutAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'teacher', 'date', 'reason', 'timestamp']
    search_fields = ['student_name', 'teacher__user__username']
    list_filter = ['date', 'teacher']
    date_hierarchy = 'date'
    ordering = ['-date', '-timestamp']


@admin.register(UnauthorizedPerson)
class UnauthorizedPersonAdmin(admin.ModelAdmin):
    list_display = ['name', 'student_name', 'guardian_name', 'relation', 'contact', 'timestamp']
    search_fields = ['name', 'student_name', 'guardian_name', 'contact']
    list_filter = ['relation', 'timestamp']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
