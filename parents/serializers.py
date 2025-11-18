from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Student, ParentGuardian, ParentMobileAccount
from teacher.models import TeacherProfile


class StudentSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.user.username', read_only=True)
    teacher_section = serializers.CharField(source='teacher.section', read_only=True)
    parents_count = serializers.SerializerMethodField()
    gender_display = serializers.CharField(source='get_gender_display', read_only=True)

    class Meta:
        model = Student
        fields = [
            'lrn',
            'name',
            'gender',
            'gender_display',
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
    student_gender = serializers.CharField(source='student.gender', read_only=True)
    teacher_name = serializers.CharField(source='teacher.user.username', read_only=True)
    has_mobile_account = serializers.SerializerMethodField()

    class Meta:
        model = ParentGuardian
        fields = [
            'id',
            'student',
            'student_name',
            'student_lrn',
            'student_gender',
            'teacher',
            'teacher_name',
            'name',
            'role',
            'contact_number',
            'email',
            'address',
            'qr_code_data',
            'has_mobile_account',
            'created_at',
        ]
        read_only_fields = ['created_at', 'teacher']
    
    def get_has_mobile_account(self, obj):
        return hasattr(obj, 'mobile_account')


class ParentMobileAccountSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    parent_name = serializers.CharField(source='parent_guardian.name', read_only=True)
    parent_role = serializers.CharField(source='parent_guardian.role', read_only=True)
    student_name = serializers.CharField(source='parent_guardian.student.name', read_only=True)
    student_lrn = serializers.CharField(source='parent_guardian.student.lrn', read_only=True)
    
    class Meta:
        model = ParentMobileAccount
        fields = [
            'id',
            'username',
            'parent_name',
            'parent_role',
            'student_name',
            'student_lrn',
            'is_active',
            'created_at',
        ]
        read_only_fields = ['created_at']


class ParentMobileRegistrationSerializer(serializers.Serializer):
    """Serializer for registering parent mobile app account"""
    parent_guardian_id = serializers.IntegerField()
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=6)
    name = serializers.CharField(max_length=100)
    
    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists.")
        return value
    
    def validate_parent_guardian_id(self, value):
        try:
            parent = ParentGuardian.objects.get(id=value)
            if hasattr(parent, 'mobile_account'):
                raise serializers.ValidationError("This parent already has a mobile account.")
        except ParentGuardian.DoesNotExist:
            raise serializers.ValidationError("Parent/Guardian not found.")
        return value
    
    def create(self, validated_data):
        parent_guardian = ParentGuardian.objects.get(id=validated_data['parent_guardian_id'])
        
        # Create user account
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            first_name=validated_data['name']
        )
        
        # Create mobile account link
        mobile_account = ParentMobileAccount.objects.create(
            user=user,
            parent_guardian=parent_guardian
        )
        
        return mobile_account


class ParentMobileLoginSerializer(serializers.Serializer):
    """Serializer for parent mobile app login"""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class RegistrationSerializer(serializers.Serializer):
    """
    Combined registration payload for student + up to 3 parent/guardian entries.
    teacher_id is optional for authenticated registrations; required for public endpoint.
    """
    teacher_id = serializers.IntegerField(required=False, allow_null=True)
    lrn = serializers.CharField(max_length=20)
    student_name = serializers.CharField(max_length=100)
    gender = serializers.ChoiceField(choices=['M', 'F'], required=False, allow_blank=True)
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
                'gender': student.gender,
                'gender_display': student.get_gender_display() if student.gender else None,
                'grade_level': student.grade_level,
                'section': student.section,
                'parents_guardians': ParentGuardianSerializer(parents, many=True).data
            })
        return result

    def get_total_students(self, obj):
        return obj.students.count()

    def get_total_parents_guardians(self, obj):
        return obj.parents_guardians.count()
