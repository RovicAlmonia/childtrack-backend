from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import Guardian

@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    list_display = [
        'name', 
        'student_name', 
        'age',
        'relationship', 
        'contact', 
        'teacher_display',
        'status_badge',
        'photo_thumbnail',
        'timestamp'
    ]
    list_filter = ['status', 'relationship', 'timestamp', 'teacher']
    search_fields = ['name', 'student_name', 'contact', 'address']
    readonly_fields = ['timestamp', 'photo_preview_large']
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Guardian Information', {
            'fields': ('teacher', 'name', 'age', 'relationship')
        }),
        ('Student Information', {
            'fields': ('student_name',)
        }),
        ('Contact Details', {
            'fields': ('contact', 'address')
        }),
        ('Status', {
            'fields': ('status',),
            'description': 'Approval status of the guardian'
        }),
        ('Photo', {
            'fields': ('photo_preview_large',),
            'description': 'Guardian photo (base64 encoded)'
        }),
        ('Metadata', {
            'fields': ('timestamp',),
            'classes': ('collapse',)
        }),
    )
    
    def teacher_display(self, obj):
        """Display teacher's full name"""
        return obj.teacher.user.get_full_name() or obj.teacher.user.username
    teacher_display.short_description = 'Teacher'
    
    def status_badge(self, obj):
        """Display status with color badge"""
        colors = {
            'pending': '#ffa500',
            'allowed': '#28a745',
            'declined': '#dc3545'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 12px; font-weight: bold;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def photo_thumbnail(self, obj):
        """Display small thumbnail in list view"""
        if obj.photo:
            return format_html(
                '<img src="data:image/jpeg;base64,{}" style="width: 40px; height: 40px; object-fit: cover; border-radius: 50%;" />',
                obj.photo
            )
        return format_html('<span style="color: #999;">No photo</span>')
    photo_thumbnail.short_description = 'Photo'
    
    def photo_preview_large(self, obj):
        """Display full-size image in detail view"""
        if obj.photo:
            return format_html(
                '<div style="margin-bottom: 15px;">'
                '<p style="color: #666; font-weight: bold; margin-bottom: 10px;">📷 Guardian Photo:</p>'
                '<img src="data:image/jpeg;base64,{}" style="max-width: 600px; max-height: 600px; object-fit: contain; border: 2px solid #2196F3; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); padding: 4px;" />'
                '</div>',
                obj.photo
            )
        return format_html('<p style="color: #999; font-style: italic;">📷 No photo uploaded yet</p>')
    photo_preview_large.short_description = 'Guardian Photo'
    
    def get_queryset(self, request):
        """Optimize queries by selecting related teacher and user"""
        qs = super().get_queryset(request)
        return qs.select_related('teacher', 'teacher__user')
    
    actions = ['mark_as_allowed', 'mark_as_declined', 'mark_as_pending']
    
    def mark_as_allowed(self, request, queryset):
        updated = queryset.update(status='allowed')
        self.message_user(request, f'{updated} guardian(s) marked as allowed.')
    mark_as_allowed.short_description = 'Mark selected as Allowed'
    
    def mark_as_declined(self, request, queryset):
        updated = queryset.update(status='declined')
        self.message_user(request, f'{updated} guardian(s) marked as declined.')
    mark_as_declined.short_description = 'Mark selected as Declined'
    
    def mark_as_pending(self, request, queryset):
        updated = queryset.update(status='pending')
        self.message_user(request, f'{updated} guardian(s) marked as pending.')
    mark_as_pending.short_description = 'Mark selected as Pending'
