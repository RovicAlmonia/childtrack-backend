from rest_framework import serializers
import base64
from django.core.files.base import ContentFile
from .models import Guardian

class GuardianSerializer(serializers.ModelSerializer):
    photo_base64 = serializers.CharField(write_only=True, required=False, allow_blank=True)
    teacher_name = serializers.CharField(source='teacher.user.get_full_name', read_only=True)
    student_id = serializers.CharField(source='student.lrn', read_only=True)
    parent_guardian_name = serializers.CharField(source='parent_guardian.name', read_only=True)
    
    class Meta:
        model = Guardian
        fields = [
            'id',
            'teacher',
            'teacher_name',
            'parent_guardian',
            'parent_guardian_name',
            'student',
            'student_id',
            'name',
            'age',
            'address',
            'relationship',
            'contact',
            'student_name',
            'photo_base64',
            'status',
            'timestamp'
        ]
        read_only_fields = ['id', 'timestamp', 'teacher_name', 'student_id', 'parent_guardian_name']
    
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
    
    def validate_status(self, value):
        """Validate status is one of the allowed choices"""
        if value not in ['pending', 'allowed', 'declined']:
            raise serializers.ValidationError("Status must be 'pending', 'allowed', or 'declined'.")
        return value
    
    def validate_photo_base64(self, value):
        """Validate base64 photo data"""
        if not value:
            return value
            
        # Strip data URI prefix if present
        if 'base64,' in value:
            value = value.split('base64,')[1]
        
        # Validate base64 string length
        if len(value) < 100:
            raise serializers.ValidationError("Invalid photo data - too short")
            
        try:
            # Try to decode to verify it's valid base64
            base64.b64decode(value)
        except Exception as e:
            raise serializers.ValidationError(f"Invalid base64 data: {str(e)}")
            
        return value
    
    def create(self, validated_data):
        """Handle base64 photo conversion on create"""
        photo_base64 = validated_data.pop('photo_base64', None)
        
        # Create the guardian instance
        guardian = Guardian.objects.create(**validated_data)
        
        # Handle photo if provided
        if photo_base64:
            try:
                # Remove data URI prefix if present
                if 'base64,' in photo_base64:
                    photo_base64 = photo_base64.split('base64,')[1]
                
                # Decode and save
                photo_data = base64.b64decode(photo_base64)
                photo_name = f"guardian_{guardian.name.replace(' ', '_')}_{guardian.student_name.replace(' ', '_')}.jpg"
                guardian.photo.save(photo_name, ContentFile(photo_data), save=True)
            except Exception as e:
                print(f"Error saving photo: {e}")
        
        return guardian
    
    def update(self, instance, validated_data):
        """Handle base64 photo conversion on update"""
        photo_base64 = validated_data.pop('photo_base64', None)
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Handle photo if provided
        if photo_base64:
            try:
                # Remove data URI prefix if present
                if 'base64,' in photo_base64:
                    photo_base64 = photo_base64.split('base64,')[1]
                
                # Decode and save
                photo_data = base64.b64decode(photo_base64)
                photo_name = f"guardian_{instance.name.replace(' ', '_')}_{instance.student_name.replace(' ', '_')}.jpg"
                instance.photo.save(photo_name, ContentFile(photo_data), save=False)
            except Exception as e:
                print(f"Error saving photo: {e}")
        
        instance.save()
        return instance
    
    def to_representation(self, instance):
        """Custom representation to include photo as base64 in responses"""
        representation = super().to_representation(instance)
        
        # Add photo as base64 if it exists
        if instance.photo:
            try:
                with instance.photo.open('rb') as photo_file:
                    photo_base64 = base64.b64encode(photo_file.read()).decode('utf-8')
                    representation['photo_base64'] = photo_base64
            except Exception as e:
                print(f"Error reading photo: {e}")
                representation['photo_base64'] = None
        else:
            representation['photo_base64'] = None
        
        return representation
