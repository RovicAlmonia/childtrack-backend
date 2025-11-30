from django.contrib import admin
from django.utils.html import format_html
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
    list_filter = ['relationship', 'timestamp', 'teacher', 'status']
    search_fields = ['name', 'student_name', 'contact', 'address']
    readonly_fields = ['timestamp', 'photo_preview']
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
            'fields': ('photo', 'photo_preview'),
            'description': 'Upload guardian photo (optional)'
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
                '<img src="{}" style="width: 40px; height: 40px; object-fit: cover; border-radius: 50%;" />',
                obj.photo.url
            )
        return format_html('<span style="color: #999;">No photo</span>')
    photo_thumbnail.short_description = 'Photo'
    
    def photo_preview(self, obj):
        """Display larger preview in detail view"""
        if obj.photo:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 300px; object-fit: contain; border: 1px solid #ddd; border-radius: 8px;" />',
                obj.photo.url
            )
        return format_html('<span style="color: #999;">No photo uploaded</span>')
    photo_preview.short_description = 'Photo Preview'
    
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
