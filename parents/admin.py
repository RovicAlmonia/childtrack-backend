from django.contrib import admin
from .models import Student, ParentGuardian, ParentMobileAccount,  MobileRegistration,  ParentNotification, ParentEvent, ParentSchedule

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


@admin.register(ParentNotification)
class ParentNotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'parent', 'student', 'type', 'message_preview', 'created_at']
    list_filter = ['type', 'created_at']
    search_fields = ['parent__name', 'parent__username', 'student__name', 'student__lrn', 'message']
    readonly_fields = ['created_at']
    autocomplete_fields = ['parent', 'student']

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
    list_display = ['id', 'parent', 'title', 'event_type', 'scheduled_at', 'created_at']
    list_filter = ['event_type', 'scheduled_at', 'created_at']
    search_fields = ['parent__name', 'parent__username', 'student__name', 'title', 'description']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['parent', 'student']

    fieldsets = (
        ('Event Target', {'fields': ('parent', 'student')}),
        ('Details', {'fields': ('title', 'description', 'event_type', 'scheduled_at', 'location')}),
        ('Extra', {'fields': ('extra_data',)}),
        ('System', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(ParentSchedule)
class ParentScheduleAdmin(admin.ModelAdmin):
    list_display = ['id', 'student', 'subject', 'day_of_week', 'time_label', 'room', 'created_at']
    list_filter = ['day_of_week', 'teacher', 'created_at']
    search_fields = ['student__name', 'student__lrn', 'subject', 'room']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['parent', 'student', 'teacher']

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



