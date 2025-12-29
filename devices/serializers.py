from rest_framework import serializers
from .models import Device


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ['id', 'user', 'token', 'platform', 'device_name', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
