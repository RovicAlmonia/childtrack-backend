from rest_framework import serializers
import base64
from django.core.files.base import ContentFile
import uuid
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
        """Handle base64 photo conversion on create - FIXED VERSION"""
        photo_base64 = validated_data.pop('photo_base64', None)
        
        # Create the guardian instance WITHOUT photo first
        guardian = Guardian.objects.create(**validated_data)
        
        # Handle photo if provided
        if photo_base64:
            try:
                # Remove data URI prefix if present (already validated but double-check)
                if 'base64,' in photo_base64:
                    photo_base64 = photo_base64.split('base64,')[1]
                
                # Decode base64 string to BYTES (this is the critical fix)
                photo_data = base64.b64decode(photo_base64)
                
                # Generate safe filename with UUID
                safe_name = guardian.name.replace(' ', '_')[:30]
                safe_student = guardian.student_name.replace(' ', '_')[:30]
                unique_id = uuid.uuid4().hex[:8]
                filename = f"guardian_{safe_name}_{safe_student}_{unique_id}.jpg"
                
                # Create ContentFile from bytes and save
                photo_file = ContentFile(photo_data, name=filename)
                guardian.photo.save(filename, photo_file, save=True)
                
                print(f"✅ Photo saved successfully: {filename} ({len(photo_data)} bytes)")
                
            except Exception as e:
                print(f"⚠️ Error saving photo: {type(e).__name__}: {e}")
                # Don't fail the entire request if photo save fails
        else:
            print("ℹ️ No photo provided in request")
        
        return guardian
    
    def update(self, instance, validated_data):
        """Handle base64 photo conversion on update - FIXED VERSION"""
        photo_base64 = validated_data.pop('photo_base64', None)
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Handle photo if provided
        if photo_base64:
            try:
                # Remove old photo if exists
                if instance.photo:
                    old_photo_path = instance.photo.path
                    instance.photo.delete(save=False)
                    print(f"🗑️ Deleted old photo: {old_photo_path}")
                
                # Remove data URI prefix if present
                if 'base64,' in photo_base64:
                    photo_base64 = photo_base64.split('base64,')[1]
                
                # Decode base64 string to BYTES
                photo_data = base64.b64decode(photo_base64)
                
                # Generate safe filename with UUID
                safe_name = instance.name.replace(' ', '_')[:30]
                safe_student = instance.student_name.replace(' ', '_')[:30]
                unique_id = uuid.uuid4().hex[:8]
                filename = f"guardian_{safe_name}_{safe_student}_{unique_id}.jpg"
                
                # Create ContentFile from bytes and save
                photo_file = ContentFile(photo_data, name=filename)
                instance.photo.save(filename, photo_file, save=False)
                
                print(f"✅ Photo updated successfully: {filename} ({len(photo_data)} bytes)")
                
            except Exception as e:
                print(f"⚠️ Error updating photo: {type(e).__name__}: {e}")
        
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
                    print(f"📤 Sending photo in response: {len(photo_base64)} chars")
            except Exception as e:
                print(f"⚠️ Error reading photo: {e}")
                representation['photo_base64'] = None
        else:
            representation['photo_base64'] = None
        
        return representation
