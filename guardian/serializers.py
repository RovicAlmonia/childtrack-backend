from rest_framework import serializers
from .models import Guardian

class GuardianSerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()
    teacher_name = serializers.CharField(source='teacher.user.get_full_name', read_only=True)
    
    class Meta:
        model = Guardian
        fields = [
            'id',
            'teacher',
            'teacher_name',
            'name',
            'age',
            'address',
            'relationship',
            'contact',
            'student_name',
            'photo',
            'photo_url',
            'timestamp'
        ]
        read_only_fields = ['id', 'timestamp', 'teacher_name', 'photo_url']
    
    def get_photo_url(self, obj):
        """Return the full URL for the photo"""
        if obj.photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.photo.url)
            return obj.photo.url
        return None
    
    def validate_age(self, value):
        """Validate that age is reasonable for a guardian"""
        if value < 18:
            raise serializers.ValidationError("Guardian must be at least 18 years old.")
        if value > 120:
            raise serializers.ValidationError("Please enter a valid age.")
        return value
    
    def validate_name(self, value):
        """Validate that name is not empty after stripping whitespace"""
        if not value or not value.strip():
            raise serializers.ValidationError("Name cannot be empty.")
        return value.strip()
    
    def validate_student_name(self, value):
        """Validate that student name is not empty after stripping whitespace"""
        if not value or not value.strip():
            raise serializers.ValidationError("Student name cannot be empty.")
        return value.strip()
