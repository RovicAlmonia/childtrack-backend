# serializers.py
from rest_framework import serializers
from .models import Student, ParentGuardian
from teacher.models import TeacherProfile


class StudentSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.user.username', read_only=True)
    teacher_section = serializers.CharField(source='teacher.section', read_only=True)
    parents_count = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'lrn',
            'name',
            'grade_level',
            'section',
            'teacher',
            'teacher_name',
            'teacher_section',
            'parents_count',
            'created_at',
        ]
        read_only_fields = ['created_at']

    def get_parents_count(self, obj):
        return obj.parents_guardians.count()


class ParentGuardianSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.name', read_only=True)
    student_lrn = serializers.CharField(source='student.lrn', read_only=True)
    teacher_name = serializers.CharField(source='teacher.user.username', read_only=True)

    class Meta:
        model = ParentGuardian
        fields = [
            'id',
            'student',
            'student_name',
            'student_lrn',
            'teacher',
            'teacher_name',
            'name',
            'role',
            'contact_number',
            'email',
            'address',
            'qr_code_data',
            'created_at',
        ]
        read_only_fields = ['created_at', 'teacher']


class RegistrationSerializer(serializers.Serializer):
    """
    Combined registration payload for student + up to 3 parent/guardian entries.
    teacher_id is optional for authenticated registrations; required for public endpoint.
    """
    teacher_id = serializers.IntegerField(required=False, allow_null=True)
    lrn = serializers.CharField(max_length=20)
    student_name = serializers.CharField(max_length=100)
    grade_level = serializers.CharField(max_length=20, required=False, allow_blank=True)
    section = serializers.CharField(max_length=50, required=False, allow_blank=True)

    parent1_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    parent1_contact = serializers.CharField(max_length=15, required=False, allow_blank=True)
    parent1_email = serializers.EmailField(required=False, allow_blank=True)

    parent2_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    parent2_contact = serializers.CharField(max_length=15, required=False, allow_blank=True)
    parent2_email = serializers.EmailField(required=False, allow_blank=True)

    guardian_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    guardian_contact = serializers.CharField(max_length=15, required=False, allow_blank=True)
    guardian_email = serializers.EmailField(required=False, allow_blank=True)

    address = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        # At least one guardian/parent name must be provided
        if not (data.get('parent1_name') or data.get('parent2_name') or data.get('guardian_name')):
            raise serializers.ValidationError("At least one parent or guardian name must be provided.")
        return data


class TeacherStudentsSerializer(serializers.ModelSerializer):
    students = serializers.SerializerMethodField()
    total_students = serializers.SerializerMethodField()
    total_parents_guardians = serializers.SerializerMethodField()

    class Meta:
        model = TeacherProfile
        fields = ['id', 'user', 'section', 'total_students', 'total_parents_guardians', 'students']

    def get_students(self, obj):
        students = obj.students.all().prefetch_related('parents_guardians')
        result = []
        for student in students:
            parents = student.parents_guardians.all()
            result.append({
                'lrn': student.lrn,
                'name': student.name,
                'grade_level': student.grade_level,
                'section': student.section,
                'parents_guardians': ParentGuardianSerializer(parents, many=True).data
            })
        return result

    def get_total_students(self, obj):
        return obj.students.count()

    def get_total_parents_guardians(self, obj):
        return obj.parents_guardians.count()
