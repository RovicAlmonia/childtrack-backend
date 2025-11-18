from django.contrib import admin
from .models import Student, ParentGuardian, ParentMobileAccount,  MobileRegistration

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['lrn', 'name', 'grade_level', 'section', 'teacher', 'created_at']
    search_fields = ['lrn', 'name', 'teacher__user__username']
    list_filter = ['grade_level', 'section', 'teacher', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Student Information', {
            'fields': ('lrn', 'name', 'grade_level', 'section')
        }),
        ('Teacher Assignment', {
            'fields': ('teacher',)
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # If user is not superuser, show only their students
        if not request.user.is_superuser:
            try:
                teacher_profile = request.user.teacherprofile
                return qs.filter(teacher=teacher_profile)
            except:
                return qs.none()
        return qs

@admin.register(ParentGuardian)
class ParentGuardianAdmin(admin.ModelAdmin):
    list_display = ['name', 'role', 'student', 'teacher', 'contact_number', 'created_at']
    search_fields = ['name', 'student__name', 'student__lrn', 'teacher__user__username']
    list_filter = ['role', 'teacher', 'created_at']
    readonly_fields = ['created_at', 'updated_at', 'qr_code_data']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('name', 'role', 'contact_number', 'email', 'address')
        }),
        ('Relationships', {
            'fields': ('student', 'teacher')
        }),
        ('QR Code Data', {
            'fields': ('qr_code_data',),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # If user is not superuser, show only their parents/guardians
        if not request.user.is_superuser:
            try:
                teacher_profile = request.user.teacherprofile
                return qs.filter(teacher=teacher_profile)
            except:
                return qs.none()
        return qs


@admin.register(ParentMobileAccount)
class ParentMobileAccountAdmin(admin.ModelAdmin):
    list_display = ['user', 'parent_guardian', 'is_active', 'created_at']
    search_fields = ['user__username', 'parent_guardian__name', 'parent_guardian__student__lrn']
    list_filter = ['is_active', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Account Information', {
            'fields': ('user', 'parent_guardian', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MobileRegistration)
class MobileRegistrationAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'is_verified', 'created_at', 'updated_at']
    search_fields = ['phone_number']
    list_filter = ['is_verified', 'created_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
