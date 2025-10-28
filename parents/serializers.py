from rest_framework import serializers
from .models import Student, ParentGuardian

class StudentSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.user.username', read_only=True)
    teacher_section = serializers.CharField(source='teacher.section', read_only=True)
    parents_guardians_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Student
        fields = ['lrn', 'name', 'grade_level', 'section', 'teacher', 'teacher_name', 
                  'teacher_section', 'parents_guardians_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
    
    def get_parents_guardians_count(self, obj):
        return obj.parents_guardians.count()

class ParentGuardianSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.name', read_only=True)
    student_lrn = serializers.CharField(source='student.lrn', read_only=True)
    teacher_name = serializers.CharField(source='teacher.user.username', read_only=True)
    
    class Meta:
        model = ParentGuardian
        fields = ['id', 'student', 'student_name', 'student_lrn', 'teacher', 'teacher_name',
                  'name', 'role', 'contact_number', 'email', 'address', 'qr_code_data', 
                  'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class RegistrationSerializer(serializers.Serializer):
    """Combined registration for student + all parents/guardians"""
    # Teacher authentication token (required)
    # Will be extracted from request.user
    
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

class StudentDetailSerializer(serializers.ModelSerializer):
    """Detailed student info with all parents/guardians"""
    teacher_name = serializers.CharField(source='teacher.user.username', read_only=True)
    teacher_section = serializers.CharField(source='teacher.section', read_only=True)
    parents_guardians = ParentGuardianSerializer(many=True, read_only=True)
    
    class Meta:
        model = Student
        fields = ['lrn', 'name', 'grade_level', 'section', 'teacher', 'teacher_name', 
                  'teacher_section', 'parents_guardians', 'created_at', 'updated_at']
