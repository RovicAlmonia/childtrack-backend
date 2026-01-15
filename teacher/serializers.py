from rest_framework import serializers
from django.contrib.auth.models import User
from .models import TeacherProfile, Attendance, Absence, Dropout, UnauthorizedPerson, ScanPhoto
from rest_framework import serializers
from .models import Attendance
from datetime import datetime
from django.utils import timezone
import pytz

class TeacherProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    name = serializers.CharField(write_only=True)  # Full name
    grade = serializers.CharField(source='section', required=False)  # Alias for section

    class Meta:
        model = TeacherProfile
        fields = ['id', 'username', 'password', 'name', 'age', 'gender', 'section', 'grade', 'contact', 'address']
        extra_kwargs = {
            'section': {'required': False},
        }

    def create(self, validated_data):
        username = validated_data.pop('username')
        password = validated_data.pop('password')
        name = validated_data.pop('name', username)  # Use name if provided, else username
        
        # Create user with full name
        user = User.objects.create_user(
            username=username, 
            password=password,
            first_name=name
        )
        teacher_profile = TeacherProfile.objects.create(user=user, **validated_data)
        return teacher_profile
from rest_framework import serializers
from .models import (
    TeacherProfile, 
    Attendance, 
    Absence, 
    Dropout, 
    UnauthorizedPerson, 
    ScanPhoto
)
from django.contrib.auth.models import User
from datetime import datetime
import pytz

# ... keep your existing TeacherProfile and User serializers ...

class AttendanceSerializer(serializers.ModelSerializer):
    time = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    
    class Meta:
        model = Attendance
        fields = [
            'id', 'teacher', 'student_name', 'student_lrn', 'gender',
            'guardian_name', 'date', 'status', 'qr_code_data',
            'timestamp', 'time', 'session', 'transaction_type'
        ]
        read_only_fields = ['id']
    
    def create(self, validated_data):
        """Handle timestamp creation with Philippines timezone"""
        # Remove 'time' from validated_data if present (we'll use it to create timestamp)
        time_str = validated_data.pop('time', None)
        timestamp = validated_data.get('timestamp')
        
        philippines_tz = pytz.timezone('Asia/Manila')
        
        # If timestamp is provided as a string, parse it
        if timestamp and isinstance(timestamp, str):
            try:
                # Try parsing ISO format with timezone: 2026-01-13T10:51:00+08:00
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                # Fallback: parse basic ISO format
                try:
                    timestamp = datetime.strptime(timestamp[:19], '%Y-%m-%dT%H:%M:%S')
                    timestamp = philippines_tz.localize(timestamp)
                except ValueError:
                    timestamp = None
        
        # If we have a time string and date, create timestamp from those
        if time_str and validated_data.get('date'):
            try:
                date_obj = validated_data['date']
                # Parse time string (HH:MM format)
                time_parts = time_str.split(':')
                hour = int(time_parts[0])
                minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                
                # Create datetime object
                dt = datetime.combine(date_obj, datetime.min.time())
                dt = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # Localize to Philippines timezone
                timestamp = philippines_tz.localize(dt)
            except (ValueError, IndexError, AttributeError) as e:
                print(f"Error parsing time: {e}")
                # Fallback to current time if parsing fails
                timestamp = datetime.now(philippines_tz)
        
        # If still no timestamp, use current Philippines time
        if not timestamp:
            timestamp = datetime.now(philippines_tz)
        
        # Ensure timestamp is timezone-aware
        if timestamp.tzinfo is None:
            timestamp = philippines_tz.localize(timestamp)
        
        validated_data['timestamp'] = timestamp
        
        print(f"📝 Creating attendance with timestamp: {timestamp} (Philippines time)")
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Handle timestamp updates with Philippines timezone"""
        # Remove 'time' from validated_data if present
        time_str = validated_data.pop('time', None)
        timestamp = validated_data.get('timestamp')
        
        philippines_tz = pytz.timezone('Asia/Manila')
        
        # If timestamp is provided as a string, parse it
        if timestamp and isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                try:
                    timestamp = datetime.strptime(timestamp[:19], '%Y-%m-%dT%H:%M:%S')
                    timestamp = philippines_tz.localize(timestamp)
                except ValueError:
                    timestamp = None
        
        # If we have a time string and date, create timestamp from those
        if time_str and (validated_data.get('date') or instance.date):
            try:
                date_obj = validated_data.get('date', instance.date)
                time_parts = time_str.split(':')
                hour = int(time_parts[0])
                minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                
                dt = datetime.combine(date_obj, datetime.min.time())
                dt = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
                timestamp = philippines_tz.localize(dt)
            except (ValueError, IndexError, AttributeError):
                pass
        
        # Ensure timestamp is timezone-aware
        if timestamp and timestamp.tzinfo is None:
            timestamp = philippines_tz.localize(timestamp)
        
        if timestamp:
            validated_data['timestamp'] = timestamp
            print(f"📝 Updating attendance with timestamp: {timestamp} (Philippines time)")
        
        return super().update(instance, validated_data)
    
    def to_representation(self, instance):
        """Convert timestamp to Philippines timezone for display"""
        data = super().to_representation(instance)
        
        if instance.timestamp:
            philippines_tz = pytz.timezone('Asia/Manila')
            
            # Convert to Philippines timezone
            if instance.timestamp.tzinfo is None:
                # Naive datetime - assume UTC and convert
                utc_time = pytz.utc.localize(instance.timestamp)
                local_time = utc_time.astimezone(philippines_tz)
            else:
                # Already has timezone info
                local_time = instance.timestamp.astimezone(philippines_tz)
            
            # Format as HH:MM (24-hour format)
            data['time'] = local_time.strftime('%H:%M')
            
            # Keep full timestamp in Philippines time
            data['timestamp'] = local_time.strftime('%H:%M')
        
        return data

# ... keep your other serializers (Absence, Dropout, etc.) ...



class AbsenceSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.user.first_name', read_only=True)

    class Meta:
        model = Absence
        fields = ['id', 'teacher', 'teacher_name', 'student_name', 'date', 'reason', 'timestamp']
        read_only_fields = ['timestamp', 'teacher']

class DropoutSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.user.first_name', read_only=True)

    class Meta:
        model = Dropout
        fields = ['id', 'teacher', 'teacher_name', 'student_name', 'date', 'reason', 'timestamp']
        read_only_fields = ['timestamp', 'teacher']

class UnauthorizedPersonSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.user.first_name', read_only=True)

    class Meta:
        model = UnauthorizedPerson
        fields = ['id', 'teacher', 'teacher_name', 'name', 'address', 'age', 'student_name', 
                  'guardian_name', 'relation', 'contact', 'photo', 'timestamp']
        read_only_fields = ['timestamp', 'teacher']



class ScanPhotoSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.user.first_name', read_only=True)
    photo_base64 = serializers.CharField(write_only=True)  # Input field from frontend
    
    class Meta:
        model = ScanPhoto
        fields = ['id', 'teacher', 'teacher_name', 'student_name', 'status', 'photo', 'photo_base64', 'timestamp']
        read_only_fields = ['timestamp', 'teacher', 'photo']  # photo is read-only, populated from photo_base64
        extra_kwargs = {
            'photo': {'required': False}  # Make photo optional since we use photo_base64
        }
    
    def create(self, validated_data):
        """
        Override create to handle photo_base64 → photo conversion
        """
        # Extract photo_base64 from validated data
        photo_base64 = validated_data.pop('photo_base64', None)
        
        # Set the photo field with the base64 data
        if photo_base64:
            validated_data['photo'] = photo_base64
        
        # Create the instance with teacher from context
        return super().create(validated_data)
    
    def validate_photo_base64(self, value):
        """
        Validate that photo_base64 is not empty and looks like valid base64
        """
        if not value or len(value) < 100:
            raise serializers.ValidationError("Photo data is too short or invalid")
        
        # Basic validation: check if it looks like base64
        import re
        if not re.match(r'^[A-Za-z0-9+/]+={0,2}$', value):
            raise serializers.ValidationError("Invalid base64 format")
        
        return value






