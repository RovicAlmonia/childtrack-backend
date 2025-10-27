from rest_framework import serializers
from .models import Student, ParentGuardian

class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ['lrn', 'name', 'grade_level', 'section', 'teacher', 'created_at']
        read_only_fields = ['created_at']

class ParentGuardianSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.name', read_only=True)
    student_lrn = serializers.CharField(source='student.lrn', read_only=True)
    
    class Meta:
        model = ParentGuardian
        fields = ['id', 'student', 'student_name', 'student_lrn', 'name', 
                  'role', 'contact_number', 'email', 'address', 'qr_code_data', 'created_at']
        read_only_fields = ['created_at']

class RegistrationSerializer(serializers.Serializer):
    """Combined registration for student + all parents/guardians"""
    lrn = serializers.CharField(max_length=20)
    student_name = serializers.CharField(max_length=100)
    grade_level = serializers.CharField(max_length=20, required=False, allow_blank=True)
    section = serializers.CharField(max_length=50, required=False, allow_blank=True)
    
    parent1_name = serializers.CharField(max_length=100)
    parent1_contact = serializers.CharField(max_length=15, required=False, allow_blank=True)
    parent1_email = serializers.EmailField(required=False, allow_blank=True)
    
    parent2_name = serializers.CharField(max_length=100)
    parent2_contact = serializers.CharField(max_length=15, required=False, allow_blank=True)
    parent2_email = serializers.EmailField(required=False, allow_blank=True)
    
    guardian_name = serializers.CharField(max_length=100)
    guardian_contact = serializers.CharField(max_length=15, required=False, allow_blank=True)
    guardian_email = serializers.EmailField(required=False, allow_blank=True)
    
    address = serializers.CharField(required=False, allow_blank=True)
