# teacher/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import TeacherProfile, Attendance, UnauthorizedPerson, ScanPhoto

@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'section', 'age', 'gender', 'contact']
    search_fields = ['user__username', 'section']
    list_filter = ['gender', 'section']

@admin.register(ScanPhoto)
class ScanPhotoAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'status', 'teacher', 'timestamp', 'photo_preview']
    search_fields = ['student_name', 'teacher__user__username']
    list_filter = ['status', 'timestamp']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    readonly_fields = ['photo_preview_large']
    
    def photo_preview(self, obj):
        """Display small thumbnail in list view"""
        if obj.photo:
            return format_html(
                '<img src="data:image/jpeg;base64,{}" style="max-width: 100px; max-height: 100px; border-radius: 4px;" />',
                obj.photo
            )
        return "No photo"
    photo_preview.short_description = "Preview"
    
    def photo_preview_large(self, obj):
        """Display full-size image in detail view"""
        if obj.photo:
            return format_html(
                '<img src="data:image/jpeg;base64,{}" style="max-width: 600px; border: 2px solid #ddd; border-radius: 8px; padding: 4px;" />',
                obj.photo
            )
        return "No photo available"
    photo_preview_large.short_description = "Captured Photo"

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'guardian_name', 'teacher', 'date', 'status', 'transaction_type', 'session', 'gender', 'timestamp']
    search_fields = ['student_name', 'student_lrn', 'guardian_name', 'teacher__user__username']
    list_filter = ['status', 'transaction_type', 'date', 'session', 'gender', 'teacher']
    date_hierarchy = 'date'
    ordering = ['-date', '-timestamp']

@admin.register(UnauthorizedPerson)
class UnauthorizedPersonAdmin(admin.ModelAdmin):
    list_display = ['name', 'student_name', 'guardian_name', 'relation', 'contact', 'timestamp', 'photo_preview']
    search_fields = ['name', 'student_name', 'guardian_name', 'contact']
    list_filter = ['relation', 'timestamp']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    readonly_fields = ['photo_preview_large']
    
    def photo_preview(self, obj):
        """Display small thumbnail in list view"""
        if obj.photo:
            return format_html(
                '<img src="data:image/jpeg;base64,{}" style="max-width: 100px; max-height: 100px; border-radius: 4px;" />',
                obj.photo
            )
        return "No photo"
    photo_preview.short_description = "Preview"
    
    def photo_preview_large(self, obj):
        """Display full-size image in detail view"""
        if obj.photo:
            return format_html(
                '<img src="data:image/jpeg;base64,{}" style="max-width: 600px; border: 2px solid #ddd; border-radius: 8px; padding: 4px;" />',
                obj.photo
            )
        return "No photo available"
    photo_preview_large.short_description = "Photo"
