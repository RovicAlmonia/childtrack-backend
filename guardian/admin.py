from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Q
from .models import Guardian
import logging

logger = logging.getLogger(__name__)

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
    list_filter = ['status', 'relationship', 'timestamp']
    search_fields = ['name', 'student_name', 'contact', 'address']
    readonly_fields = ['timestamp', 'photo_preview']
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Guardian Information', {
            'fields': ('teacher', 'name', 'age', 'relationship')
        }),
        ('Student Information', {
            'fields': ('student_name', 'student', 'parent_guardian')
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
        """Display teacher's full name with better error handling"""
        try:
            if not obj.teacher:
                return format_html('<span style="color: #999;">No Teacher</span>')
            
            if not hasattr(obj.teacher, 'user') or not obj.teacher.user:
                return format_html('<span style="color: #dc3545;">Teacher Missing User</span>')
            
            full_name = obj.teacher.user.get_full_name()
            if full_name:
                return full_name
            
            return obj.teacher.user.username or 'Unknown'
            
        except AttributeError as e:
            logger.error(f"AttributeError in teacher_display for guardian {obj.id}: {e}")
            return format_html('<span style="color: #dc3545;">Error</span>')
        except Exception as e:
            logger.error(f"Unexpected error in teacher_display for guardian {obj.id}: {e}")
            return format_html('<span style="color: #dc3545;">Error</span>')
    
    teacher_display.short_description = 'Teacher'
    
    def status_badge(self, obj):
        """Display status with color badge"""
        try:
            colors = {
                'pending': '#ffa500',
                'allowed': '#28a745',
                'declined': '#dc3545'
            }
            return format_html(
                '<span style="background-color: {}; color: white; padding: 3px 10px; '
                'border-radius: 12px; font-weight: bold; font-size: 11px;">{}</span>',
                colors.get(obj.status, '#6c757d'),
                obj.get_status_display()
            )
        except Exception as e:
            logger.error(f"Error in status_badge for guardian {obj.id}: {e}")
            return obj.status
    
    status_badge.short_description = 'Status'
    
    def photo_thumbnail(self, obj):
        """Display small thumbnail in list view with better error handling"""
        try:
            if not obj.photo:
                return format_html('<span style="color: #999; font-size: 11px;">No photo</span>')
            
            if not obj.photo.name:
                return format_html('<span style="color: #dc3545; font-size: 11px;">Missing file</span>')
            
            try:
                photo_url = obj.photo.url
            except (ValueError, AttributeError) as e:
                logger.error(f"Error getting photo URL for guardian {obj.id}: {e}")
                return format_html('<span style="color: #dc3545; font-size: 11px;">URL Error</span>')
            
            return format_html(
                '<img src="{}" style="width: 40px; height: 40px; object-fit: cover; '
                'border-radius: 50%; border: 2px solid #ddd;" '
                'onerror="this.style.display=\'none\'; this.nextSibling.style.display=\'inline\';" />'
                '<span style="display:none; color: #999; font-size: 11px;">Load failed</span>',
                photo_url
            )
        except Exception as e:
            logger.error(f"Unexpected error in photo_thumbnail for guardian {obj.id}: {e}")
            return format_html('<span style="color: #dc3545; font-size: 11px;">Error</span>')
    
    photo_thumbnail.short_description = 'Photo'
    
    def photo_preview(self, obj):
        """Display larger preview in detail view"""
        try:
            if not obj.photo:
                return format_html(
                    '<div style="padding: 20px; background: #f8f9fa; border-radius: 8px; text-align: center;">'
                    '<p style="color: #999; margin: 0;">No photo uploaded</p>'
                    '</div>'
                )
            
            if not obj.photo.name:
                return format_html(
                    '<div style="padding: 20px; background: #fff3cd; border-radius: 8px; text-align: center;">'
                    '<p style="color: #856404; margin: 0;">Photo file is missing</p>'
                    '</div>'
                )
            
            try:
                photo_url = obj.photo.url
            except (ValueError, AttributeError) as e:
                logger.error(f"Error getting photo URL for guardian {obj.id}: {e}")
                return format_html(
                    '<div style="padding: 20px; background: #f8d7da; border-radius: 8px; text-align: center;">'
                    '<p style="color: #721c24; margin: 0;">Error loading photo URL</p>'
                    '<p style="color: #721c24; margin: 5px 0 0 0; font-size: 12px;">{}</p>'
                    '</div>',
                    str(e)
                )
            
            return format_html(
                '<div style="text-align: center;">'
                '<img src="{}" style="max-width: 300px; max-height: 300px; object-fit: contain; '
                'border: 1px solid #ddd; border-radius: 8px;" '
                'onerror="this.style.display=\'none\'; this.nextSibling.style.display=\'block\';" />'
                '<div style="display:none; padding: 20px; background: #f8d7da; border-radius: 8px;">'
                '<p style="color: #721c24; margin: 0;">Failed to load image</p>'
                '</div>'
                '</div>',
                photo_url
            )
        except Exception as e:
            logger.error(f"Unexpected error in photo_preview for guardian {obj.id}: {e}")
            return format_html(
                '<div style="padding: 20px; background: #f8d7da; border-radius: 8px; text-align: center;">'
                '<p style="color: #721c24; margin: 0;">Error: {}</p>'
                '</div>',
                str(e)
            )
    
    photo_preview.short_description = 'Photo Preview'
    
    def get_queryset(self, request):
        """Optimize queries - removed select_related to avoid issues with nullable FKs"""
        qs = super().get_queryset(request)
        # Don't use select_related or prefetch_related for now to isolate the issue
        return qs
    
    actions = ['mark_as_allowed', 'mark_as_declined', 'mark_as_pending']
    
    @admin.action(description='Mark selected as Allowed')
    def mark_as_allowed(self, request, queryset):
        updated = queryset.update(status='allowed')
        self.message_user(request, f'{updated} guardian(s) marked as allowed.')
    
    @admin.action(description='Mark selected as Declined')
    def mark_as_declined(self, request, queryset):
        updated = queryset.update(status='declined')
        self.message_user(request, f'{updated} guardian(s) marked as declined.')
    
    @admin.action(description='Mark selected as Pending')
    def mark_as_pending(self, request, queryset):
        updated = queryset.update(status='pending')
        self.message_user(request, f'{updated} guardian(s) marked as pending.')
