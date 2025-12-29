from django.db import models
from django.conf import settings


class Device(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    token = models.CharField(max_length=512, unique=True)
    platform = models.CharField(max_length=32, blank=True, null=True)
    device_name = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.platform or 'device'} - {self.token[:12]}"
