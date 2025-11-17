from django.contrib import admin
from .models import Guardian

@admin.ModelAdmin
class GuardianAdmin(admin.ModelAdmin):
    list_display = ['name', 'student_name', 'relationship', 'contact', 'teacher', 'timestamp']
    list_filter = ['relationship', 'timestamp', 'teacher']
    search_fields = ['name', 'student_name', 'contact']
    readonly_fields = ['timestamp']
    
    fieldsets = (
        ('Guardian Information', {
            'fields': ('teacher', 'name', 'age', 'relationship', 'photo')
        }),
        ('Student Information', {
            'fields': ('student_name',)
        }),
        ('Contact Details', {
            'fields': ('contact', 'address')
        }),
        ('Metadata', {
            'fields': ('timestamp',)
        }),
    )

admin.site.register(Guardian, GuardianAdmin)
