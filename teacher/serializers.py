from rest_framework import serializers
from django.contrib.auth.models import User
from .models import TeacherProfile, Attendance

class TeacherProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    
    class Meta:
        model = TeacherProfile
        fields = ['id', 'username', 'password', 'age', 'gender', 'section', 'contact', 'address']
    
    def create(self, validated_data):
        username = validated_data.pop('username')
        password = validated_data.pop('password')
        user = User.objects.create_user(username=username, password=password)
        teacher_profile = TeacherProfile.objects.create(user=user, **validated_data)
        return teacher_profile

class AttendanceSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.user.username', read_only=True)
    
    class Meta:
        model = Attendance
        fields = [
            'id', 'teacher', 'teacher_name', 'student_name', 'qr_code_data', 'timestamp',
            'guardian_name', 'guardian_age', 'guardian_address', 
            'guardian_relationship', 'guardian_contact', 'is_unregistered'
        ]

# Remove UnregisteredGuardianSerializer
