from django.contrib import admin
from .models import Guardian

@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    list_display = ['name', 'student_name', 'relationship', 'contact', 'teacher', 'timestamp']
    search_fields = ['name', 'student_name', 'contact']
    list_filter = ['relationship', 'timestamp', 'teacher']
    readonly_fields = ['timestamp']
    
    fieldsets = (
        ('Guardian Information', {
            'fields': ('name', 'age', 'address', 'relationship', 'contact')
        }),
        ('Student & Teacher', {
            'fields': ('student_name', 'teacher', 'timestamp')
        }),
    )
