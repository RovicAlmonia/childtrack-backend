from rest_framework import serializers
from django.contrib.auth.models import User
from .models import TeacherProfile, Attendance, UnauthorizedPerson


class TeacherProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for TeacherProfile model.
    Handles user creation during registration.
    """
    username = serializers.CharField(write_only=True, required=True)
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    grade = serializers.CharField(source='section', required=False)
    
    class Meta:
        model = TeacherProfile
        fields = [
            'id', 
            'username', 
            'password', 
            'name', 
            'age', 
            'gender', 
            'section', 
            'grade', 
            'contact', 
            'address'
        ]
        extra_kwargs = {
            'section': {'required': False},
            'age': {'required': True},
            'gender': {'required': True},
            'contact': {'required': True},
            'address': {'required': True},
        }
    
    def validate_username(self, value):
        """Check if username already exists"""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists.")
        return value
    
    def validate_age(self, value):
        """Validate age is reasonable"""
        if value < 18 or value > 100:
            raise serializers.ValidationError("Age must be between 18 and 100.")
        return value
    
    def validate_contact(self, value):
        """Validate contact number format"""
        if not value.replace('+', '').replace('-', '').replace(' ', '').isdigit():
            raise serializers.ValidationError("Contact must contain only numbers, spaces, hyphens, or plus sign.")
        return value
    
    def create(self, validated_data):
        """Create User and TeacherProfile"""
        username = validated_data.pop('username')
        password = validated_data.pop('password')
        name = validated_data.get('name')
        
        # Create the User
        user = User.objects.create_user(
            username=username, 
            password=password,
            first_name=name
        )
        
        # Create the TeacherProfile
        teacher_profile = TeacherProfile.objects.create(user=user, **validated_data)
        return teacher_profile


class AttendanceSerializer(serializers.ModelSerializer):
    """
    Serializer for Attendance model.
    Provides additional fields for QR data and teacher information.
    """
    teacher_name = serializers.CharField(source='teacher.name', read_only=True)
    lrn = serializers.CharField(source='student_lrn', required=False, allow_blank=True)
    qr_data = serializers.CharField(source='qr_code_data', required=False, allow_blank=True)
    
    class Meta:
        model = Attendance
        fields = [
            'id', 
            'teacher', 
            'teacher_name', 
            'student_name', 
            'student_lrn', 
            'lrn', 
            'gender', 
            'date', 
            'status', 
            'session', 
            'qr_code_data', 
            'qr_data', 
            'reason',
            'timestamp'
        ]
        read_only_fields = ['timestamp', 'teacher']
        extra_kwargs = {
            'teacher': {'required': False},
            'student_name': {'required': True},
            'date': {'required': True},
            'status': {'required': True},
        }
    
    def validate_student_name(self, value):
        """Validate student name is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Student name cannot be empty.")
        return value.strip()
    
    def validate_session(self, value):
        """Validate session is AM or PM"""
        if value and value.upper() not in ['AM', 'PM']:
            raise serializers.ValidationError("Session must be either 'AM' or 'PM'.")
        return value.upper() if value else None
    
    def validate(self, data):
        """Cross-field validation"""
        # Ensure status is valid
        valid_statuses = ['Present', 'Absent', 'Late', 'Drop-off', 'Pick-up', 'Dropped Out']
        if 'status' in data and data['status'] not in valid_statuses:
            raise serializers.ValidationError({
                'status': f"Status must be one of: {', '.join(valid_statuses)}"
            })
        
        return data


class UnauthorizedPersonSerializer(serializers.ModelSerializer):
    """
    Serializer for UnauthorizedPerson model.
    Tracks unauthorized access attempts.
    """
    teacher_name = serializers.CharField(source='teacher.name', read_only=True)
    
    class Meta:
        model = UnauthorizedPerson
        fields = [
            'id', 
            'teacher', 
            'teacher_name', 
            'name', 
            'address', 
            'age', 
            'student_name', 
            'guardian_name', 
            'relation', 
            'contact', 
            'photo', 
            'timestamp'
        ]
        read_only_fields = ['timestamp', 'teacher']
        extra_kwargs = {
            'teacher': {'required': False},
            'name': {'required': True},
            'address': {'required': True},
            'age': {'required': True},
            'student_name': {'required': True},
            'guardian_name': {'required': True},
            'relation': {'required': True},
            'contact': {'required': True},
        }
    
    def validate_name(self, value):
        """Validate name is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Name cannot be empty.")
        return value.strip()
    
    def validate_student_name(self, value):
        """Validate student name is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Student name cannot be empty.")
        return value.strip()
    
    def validate_guardian_name(self, value):
        """Validate guardian name is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Guardian name cannot be empty.")
        return value.strip()
    
    def validate_age(self, value):
        """Validate age is reasonable"""
        if value < 0 or value > 150:
            raise serializers.ValidationError("Age must be between 0 and 150.")
        return value
    
    def validate_contact(self, value):
        """Validate contact number format"""
        if not value.replace('+', '').replace('-', '').replace(' ', '').isdigit():
            raise serializers.ValidationError("Contact must contain only numbers, spaces, hyphens, or plus sign.")
        return value
