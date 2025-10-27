from django.contrib import admin
from .models import Student, ParentGuardian

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['lrn', 'name', 'grade_level', 'section', 'teacher', 'created_at']
    search_fields = ['lrn', 'name']
    list_filter = ['grade_level', 'section', 'teacher']
    readonly_fields = ['created_at']

@admin.register(ParentGuardian)
class ParentGuardianAdmin(admin.ModelAdmin):
    list_display = ['name', 'role', 'student', 'contact_number', 'email', 'created_at']
    search_fields = ['name', 'student__name', 'student__lrn']
    list_filter = ['role', 'created_at']
    readonly_fields = ['created_at', 'qr_code_data']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('name', 'role', 'contact_number', 'email', 'address')
        }),
        ('Student Information', {
            'fields': ('student',)
        }),
        ('QR Code Data', {
            'fields': ('qr_code_data',),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
