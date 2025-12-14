from rest_framework import serializers
from django.contrib.auth.models import User
from .models import TeacherProfile, Attendance, Absence, Dropout, UnauthorizedPerson, ScanPhoto

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

class AttendanceSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.user.first_name', read_only=True)
    lrn = serializers.CharField(source='student_lrn', required=False)
    qr_data = serializers.CharField(source='qr_code_data', required=False)  # Alias for qr_code_data
    parent = serializers.CharField(source='guardian_name', required=False)  # Alias for guardian_name

    class Meta:
        model = Attendance
        fields = ['id', 'teacher', 'teacher_name', 'student_name', 'student_lrn', 'lrn', 'gender', 
                  'guardian_name', 'parent', 'date', 'status', 'session', 'transaction_type',
                  'qr_code_data', 'qr_data', 'timestamp']
        read_only_fields = ['timestamp', 'teacher']

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


