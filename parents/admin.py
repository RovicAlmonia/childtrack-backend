from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import Student, ParentGuardian, ParentMobileAccount, MobileRegistration, ParentNotification, ParentEvent, ParentSchedule

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
    list_display = ['username', 'name', 'role', 'student', 'teacher', 'avatar_thumbnail', 'contact_number', 'created_at']
    search_fields = ['username', 'name', 'student__name', 'student__lrn', 'teacher__user__username']
    list_filter = ['role', 'teacher', 'created_at']
    readonly_fields = ['created_at', 'updated_at', 'qr_code_data', 'avatar_preview']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('username', 'name', 'password', 'role', 'contact_number', 'email', 'address')
        }),
        ('Relationships', {
            'fields': ('student', 'teacher')
        }),
        ('QR Code Data', {
            'fields': ('qr_code_data',),
            'classes': ('collapse',)
        }),
        ('Photo', {
            'fields': ('avatar', 'avatar_preview'),
            'description': 'Upload parent avatar (optional)'
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

    def avatar_thumbnail(self, obj):
        """Display small thumbnail in list view"""
        if getattr(obj, 'avatar', None):
            try:
                return format_html(
                    '<img src="{}" style="width: 40px; height: 40px; object-fit: cover; border-radius: 50%;" />',
                    obj.avatar.url
                )
            except Exception:
                return 'No photo'
        return format_html('<span style="color: #999;">No photo</span>')
    avatar_thumbnail.short_description = 'Avatar'

    def avatar_preview(self, obj):
        """Display larger preview in detail view with live preview for new uploads"""
        # Reuse the same robust preview HTML used in guardian admin
        if getattr(obj, 'avatar', None):
            try:
                existing_avatar = format_html(
                    '''<div style="margin-bottom: 15px;">
                        <p style="color: #666; font-weight: bold; margin-bottom: 10px;">✅ Current avatar:</p>
                        <img src="{}" style="max-width: 400px; max-height: 400px; object-fit: contain; border: 2px solid #2196F3; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" 
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='block';" />
                        <p style="display: none; color: #d32f2f; padding: 10px; background-color: #ffebee; border-radius: 4px;">
                            ⚠️ Error loading image. File path: {}
                        </p>
                        <p style="color: #999; font-size: 12px; margin-top: 8px;">
                            Avatar URL: <a href="{}" target="_blank">{}</a>
                        </p>
                    </div>''',
                    obj.avatar.url,
                    obj.avatar.url,
                    obj.avatar.url
                )
            except Exception as e:
                existing_avatar = format_html('<p style="color: #d32f2f;">Error loading avatar: {}</p>', str(e))
        else:
            existing_avatar = '<p style="color: #999; font-style: italic;">📷 No avatar uploaded yet</p>'

        preview_html = '''
        <div id="avatar-preview-container" style="margin-top: 10px;">
            {existing}
            <div id="avatar-preview-new" style="display: none; margin-top: 15px; padding: 10px; background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 8px;">
                <p style="color: #666; font-weight: bold; margin-bottom: 10px;">📷 New avatar preview:</p>
                <img id="avatar-preview-img" src="" style="max-width: 400px; max-height: 400px; object-fit: contain; border: 2px solid #4CAF50; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" />
            </div>
        </div>
        <script>
            (function() {{
                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', initAvatarPreview);
                }} else {{
                    initAvatarPreview();
                }}

                function initAvatarPreview() {{
                    const avatarInput = document.querySelector('input[name="avatar"]');
                    if (!avatarInput) {{
                        // fallback to photo if present
                        const other = document.querySelector('input[name="photo"]');
                        if (other) avatarInput = other;
                    }}
                    if (!avatarInput) {{
                        return;
                    }}

                    avatarInput.addEventListener('change', function(e) {{
                        const file = e.target.files[0];
                        const previewContainer = document.getElementById('avatar-preview-new');
                        const previewImg = document.getElementById('avatar-preview-img');

                        if (file && file.type.startsWith('image/')) {{
                            const reader = new FileReader();
                            reader.onload = function(ev) {{
                                previewImg.src = ev.target.result;
                                previewContainer.style.display = 'block';
                            }};
                            reader.onerror = function(ev) {{
                                console.error('Error reading file:', ev);
                            }};
                            reader.readAsDataURL(file);
                        }} else {{
                            previewContainer.style.display = 'none';
                            if (file) {{
                                alert('Please select a valid image file.');
                            }}
                        }}
                    }});

                    // Handle clear checkbox
                    const clearCheckbox = document.querySelector('input[name="avatar-clear"]');
                    if (clearCheckbox) {{
                        clearCheckbox.addEventListener('change', function(e) {{
                            const previewContainer = document.getElementById('avatar-preview-new');
                            if (e.target.checked) {{
                                previewContainer.style.display = 'none';
                            }}
                        }});
                    }}
                }}
            }})();
        </script>
        '''

        return mark_safe(preview_html.format(existing=existing_avatar))
    avatar_preview.short_description = 'Avatar Preview'


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


@admin.register(ParentNotification)
class ParentNotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'parent', 'student', 'type', 'message_preview', 'created_at']
    list_filter = ['type', 'created_at']
    search_fields = ['parent__name', 'parent__username', 'student__name', 'student__lrn', 'message']
    readonly_fields = ['created_at']
    # REMOVED autocomplete_fields - using raw_id_fields instead
    raw_id_fields = ['parent', 'student']

    fieldsets = (
        ('Notification Target', {
            'fields': ('parent', 'student')
        }),
        ('Content', {
            'fields': ('type', 'message', 'extra_data')
        }),
        ('System', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )

    def message_preview(self, obj):
        return (obj.message[:50] + '...') if obj.message and len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message'


@admin.register(ParentEvent)
class ParentEventAdmin(admin.ModelAdmin):
    list_display = ['id', 'teacher', 'title', 'event_type', 'section', 'scheduled_at', 'created_at']
    list_filter = ['event_type', 'section', 'teacher', 'scheduled_at', 'created_at']
    search_fields = ['title', 'description', 'teacher__user__username', 'parent__name', 'student__name', 'student__lrn']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['parent', 'student']
    fieldsets = (
        ('Event Details', {'fields': ('title', 'description', 'event_type', 'scheduled_at', 'location')}),
        ('Target', {'fields': ('teacher', 'section', 'parent', 'student')}),
        ('Extra', {'fields': ('extra_data',)}),
        ('System', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    
    def get_queryset(self, request):
        """Return all events; superusers see all, regular teachers see only their own."""
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            try:
                teacher_profile = request.user.teacherprofile
                qs = qs.filter(teacher=teacher_profile)
            except:
                # If user is not a teacher, show nothing
                qs = qs.none()
        return qs
    
@admin.register(ParentSchedule)
class ParentScheduleAdmin(admin.ModelAdmin):
    list_display = ['id', 'student', 'subject', 'day_of_week', 'time_label', 'room', 'created_at']
    list_filter = ['day_of_week', 'teacher', 'created_at']
    search_fields = ['student__name', 'student__lrn', 'subject', 'room']
    readonly_fields = ['created_at', 'updated_at']
    # REMOVED autocomplete_fields - using raw_id_fields instead
    raw_id_fields = ['parent', 'student', 'teacher']

    fieldsets = (
        ('Associations', {'fields': ('student', 'parent', 'teacher')}),
        (
            'Schedule Details',
            {
                'fields': (
                    'subject',
                    'description',
                    'day_of_week',
                    ('start_time', 'end_time'),
                    'time_label',
                    'room',
                    'icon',
                )
            },
        ),
        ('Extra', {'fields': ('extra_data',)}),
        ('System', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )





