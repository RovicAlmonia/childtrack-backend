# admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Q
from .models import TeacherProfile, Attendance, Absence, Dropout, UnauthorizedPerson


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ['get_teacher_name', 'username', 'section', 'gender', 'age', 'contact', 'get_attendance_count']
    list_filter = ['gender', 'section']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'section', 'contact']
    readonly_fields = ['user', 'get_attendance_count', 'get_absence_count']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Personal Information', {
            'fields': ('age', 'gender', 'contact', 'address')
        }),
        ('Professional Information', {
            'fields': ('section',)
        }),
        ('Statistics', {
            'fields': ('get_attendance_count', 'get_absence_count'),
            'classes': ('collapse',)
        }),
    )
    
    def get_teacher_name(self, obj):
        full_name = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return full_name if full_name else obj.user.username
    get_teacher_name.short_description = 'Teacher Name'
    get_teacher_name.admin_order_field = 'user__first_name'
    
    def username(self, obj):
        return obj.user.username
    username.short_description = 'Username'
    username.admin_order_field = 'user__username'
    
    def get_attendance_count(self, obj):
        count = obj.attendances.count()
        return format_html('<span style="color: #28a745; font-weight: bold;">{}</span>', count)
    get_attendance_count.short_description = 'Total Attendance Records'
    
    def get_absence_count(self, obj):
        count = obj.absences.count()
        return format_html('<span style="color: #dc3545; font-weight: bold;">{}</span>', count)
    get_absence_count.short_description = 'Total Absence Records'


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = [
        'student_name', 
        'student_lrn', 
        'date', 
        'session',
        'status',
        'get_teacher_name',
        'get_section',
        'timestamp'
    ]
    list_filter = [
        'status', 
        'session',
        'date', 
        'teacher__section',
        'teacher'
    ]
    search_fields = [
        'student_name', 
        'student_lrn', 
        'teacher__user__username',
        'teacher__user__first_name',
        'teacher__section',
        'qr_code_data'
    ]
    date_hierarchy = 'date'
    ordering = ['-date', '-timestamp']
    
    # Make status and session editable directly in the list view
    list_editable = ['status', 'session']
    
    # Fields to display when viewing/editing an individual record - ALL EDITABLE
    fieldsets = (
        ('Student Information', {
            'fields': ('student_name', 'student_lrn')
        }),
        ('Attendance Details', {
            'fields': ('teacher', 'date', 'session', 'status')
        }),
        ('Additional Information', {
            'fields': ('qr_code_data', 'timestamp'),
            'classes': ('collapse',)
        }),
    )
    
    # Make timestamp read-only but everything else editable
    readonly_fields = ['timestamp']
    
    # Show 50 records per page
    list_per_page = 50
    
    def get_teacher_name(self, obj):
        full_name = f"{obj.teacher.user.first_name} {obj.teacher.user.last_name}".strip()
        return full_name if full_name else obj.teacher.user.username
    get_teacher_name.short_description = 'Teacher'
    get_teacher_name.admin_order_field = 'teacher__user__first_name'
    
    def get_section(self, obj):
        return obj.teacher.section
    get_section.short_description = 'Section'
    get_section.admin_order_field = 'teacher__section'
    
    # Add custom bulk actions
    actions = [
        'mark_as_present', 
        'mark_as_absent', 
        'mark_as_late', 
        'mark_as_drop_off', 
        'mark_as_pick_up', 
        'mark_as_am', 
        'mark_as_pm'
    ]
    
    def mark_as_present(self, request, queryset):
        updated = queryset.update(status='Present')
        self.message_user(request, f'{updated} attendance record(s) marked as Present.')
    mark_as_present.short_description = '✅ Mark selected as Present'
    
    def mark_as_absent(self, request, queryset):
        updated = queryset.update(status='Absent')
        self.message_user(request, f'{updated} attendance record(s) marked as Absent.')
    mark_as_absent.short_description = '❌ Mark selected as Absent'
    
    def mark_as_late(self, request, queryset):
        updated = queryset.update(status='Late')
        self.message_user(request, f'{updated} attendance record(s) marked as Late.')
    mark_as_late.short_description = '⏰ Mark selected as Late'
    
    def mark_as_drop_off(self, request, queryset):
        updated = queryset.update(status='Drop-off')
        self.message_user(request, f'{updated} attendance record(s) marked as Drop-off.')
    mark_as_drop_off.short_description = '🌅 Mark selected as Drop-off'
    
    def mark_as_pick_up(self, request, queryset):
        updated = queryset.update(status='Pick-up')
        self.message_user(request, f'{updated} attendance record(s) marked as Pick-up.')
    mark_as_pick_up.short_description = '🌇 Mark selected as Pick-up'
    
    def mark_as_am(self, request, queryset):
        updated = queryset.update(session='AM')
        self.message_user(request, f'{updated} attendance record(s) set to AM session.')
    mark_as_am.short_description = '🌅 Set session to AM'
    
    def mark_as_pm(self, request, queryset):
        updated = queryset.update(session='PM')
        self.message_user(request, f'{updated} attendance record(s) set to PM session.')
    mark_as_pm.short_description = '🌇 Set session to PM'
    
    # Override to allow editing all fields
    def get_readonly_fields(self, request, obj=None):
        # Only timestamp is readonly
        return ['timestamp']


@admin.register(Absence)
class AbsenceAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'date', 'get_teacher_name', 'get_section', 'reason_preview', 'timestamp']
    list_filter = ['date', 'teacher__section', 'teacher']
    search_fields = ['student_name', 'reason', 'teacher__user__username', 'teacher__user__first_name']
    date_hierarchy = 'date'
    ordering = ['-date', '-timestamp']
    list_per_page = 50
    
    fieldsets = (
        ('Student Information', {
            'fields': ('student_name',)
        }),
        ('Absence Details', {
            'fields': ('teacher', 'date', 'reason')
        }),
        ('Metadata', {
            'fields': ('timestamp',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['timestamp']
    
    def get_teacher_name(self, obj):
        full_name = f"{obj.teacher.user.first_name} {obj.teacher.user.last_name}".strip()
        return full_name if full_name else obj.teacher.user.username
    get_teacher_name.short_description = 'Teacher'
    get_teacher_name.admin_order_field = 'teacher__user__first_name'
    
    def get_section(self, obj):
        return obj.teacher.section
    get_section.short_description = 'Section'
    get_section.admin_order_field = 'teacher__section'
    
    def reason_preview(self, obj):
        if len(obj.reason) > 60:
            return format_html(
                '<span title="{}">{}</span>',
                obj.reason,
                obj.reason[:60] + '...'
            )
        return obj.reason
    reason_preview.short_description = 'Reason'


@admin.register(Dropout)
class DropoutAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'date', 'get_teacher_name', 'get_section', 'reason_preview', 'timestamp']
    list_filter = ['date', 'teacher__section', 'teacher']
    search_fields = ['student_name', 'reason', 'teacher__user__username', 'teacher__user__first_name']
    date_hierarchy = 'date'
    ordering = ['-date', '-timestamp']
    list_per_page = 50
    
    fieldsets = (
        ('Student Information', {
            'fields': ('student_name',)
        }),
        ('Dropout Details', {
            'fields': ('teacher', 'date', 'reason')
        }),
        ('Metadata', {
            'fields': ('timestamp',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['timestamp']
    
    def get_teacher_name(self, obj):
        full_name = f"{obj.teacher.user.first_name} {obj.teacher.user.last_name}".strip()
        return full_name if full_name else obj.teacher.user.username
    get_teacher_name.short_description = 'Teacher'
    get_teacher_name.admin_order_field = 'teacher__user__first_name'
    
    def get_section(self, obj):
        return obj.teacher.section
    get_section.short_description = 'Section'
    get_section.admin_order_field = 'teacher__section'
    
    def reason_preview(self, obj):
        if len(obj.reason) > 60:
            return format_html(
                '<span title="{}">{}</span>',
                obj.reason,
                obj.reason[:60] + '...'
            )
        return obj.reason
    reason_preview.short_description = 'Reason'


@admin.register(UnauthorizedPerson)
class UnauthorizedPersonAdmin(admin.ModelAdmin):
    list_display = [
        'name', 
        'age', 
        'student_name', 
        'guardian_name', 
        'relation',
        'contact',
        'get_teacher_name',
        'get_section',
        'timestamp'
    ]
    list_filter = ['relation', 'teacher__section', 'teacher', 'timestamp']
    search_fields = [
        'name', 
        'student_name', 
        'guardian_name', 
        'contact',
        'address',
        'teacher__user__username',
        'teacher__user__first_name'
    ]
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    list_per_page = 50
    
    fieldsets = (
        ('Person Information', {
            'fields': ('name', 'age', 'address', 'contact')
        }),
        ('Related Information', {
            'fields': ('student_name', 'guardian_name', 'relation')
        }),
        ('Teacher & Documentation', {
            'fields': ('teacher', 'photo')
        }),
        ('Metadata', {
            'fields': ('timestamp',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['timestamp']
    
    def get_teacher_name(self, obj):
        full_name = f"{obj.teacher.user.first_name} {obj.teacher.user.last_name}".strip()
        return full_name if full_name else obj.teacher.user.username
    get_teacher_name.short_description = 'Reported By'
    get_teacher_name.admin_order_field = 'teacher__user__first_name'
    
    def get_section(self, obj):
        return obj.teacher.section
    get_section.short_description = 'Section'
    get_section.admin_order_field = 'teacher__section'


# Customize admin site header and title
admin.site.site_header = 'ChildTrack Administration Portal'
admin.site.site_title = 'ChildTrack Admin'
admin.site.index_title = 'ChildTrack Management Dashboard'
