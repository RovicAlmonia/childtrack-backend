from django.contrib import admin
from .models import Device


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('id', 'platform', 'device_name', 'user', 'created_at')
    search_fields = ('device_name', 'token')
    readonly_fields = ('created_at', 'updated_at')
