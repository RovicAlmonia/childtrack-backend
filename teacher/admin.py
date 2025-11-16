from django.contrib import admin
from .models import TeacherProfile, Attendance, Dropout, UnauthorizedPerson

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
    
    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            if obj.status == 'Dropped Out':
                Dropout.objects.create(
                    teacher=obj.teacher,
                    student_name=obj.student_name,
                    student_lrn=obj.student_lrn,
                    gender=obj.gender,
                    date=obj.date,
                    reason='Changed to dropout from admin panel'
                )
                obj.delete()
                return
        super().save_model(request, obj, form, change)

@admin.register(Dropout)
class DropoutAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'teacher', 'date', 'reason', 'gender', 'timestamp']
    search_fields = ['student_name', 'student_lrn', 'teacher__user__username', 'reason']
    list_filter = ['date', 'teacher', 'gender']
    date_hierarchy = 'date'
    ordering = ['-date', '-timestamp']

@admin.register(UnauthorizedPerson)
class UnauthorizedPersonAdmin(admin.ModelAdmin):
    list_display = ['name', 'student_name', 'guardian_name', 'relation', 'contact', 'timestamp']
    search_fields = ['name', 'student_name', 'guardian_name', 'contact']
    list_filter = ['relation', 'timestamp']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
