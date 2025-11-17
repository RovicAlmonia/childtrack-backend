from rest_framework import serializers
from .models import Guardian

class GuardianSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.user.username', read_only=True)
    photo_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Guardian
        fields = ['id', 'teacher', 'teacher_name', 'name', 'age', 'address', 
                  'relationship', 'contact', 'student_name', 'photo', 'photo_url', 'timestamp']
        read_only_fields = ['timestamp', 'photo_url']
    
    def get_photo_url(self, obj):
        """Return full URL for photo if it exists"""
        if obj.photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.photo.url)
            return obj.photo.url
        return None

