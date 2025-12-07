from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Student, ParentGuardian, ParentMobileAccount, ParentNotification, ParentEvent, ParentSchedule
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
    student_section = serializers.CharField(source='student.section', read_only=True)
    student_gender = serializers.CharField(source='student.gender', read_only=True)
    teacher_name = serializers.CharField(source='teacher.user.username', read_only=True)
    has_mobile_account = serializers.SerializerMethodField()
    password = serializers.CharField(max_length=100, required=False, allow_blank=True)
    must_change_credentials = serializers.BooleanField(read_only=True)
    # Raw ImageField for uploads
    avatar = serializers.ImageField(required=False, allow_null=True)
    # Public URL for the avatar (always returns full Cloudinary URL)
    avatar_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ParentGuardian
        fields = [
            'id',
            'student',
            'student_name',
            'student_lrn',
            'student_section',
            'student_gender',
            'teacher',
            'teacher_name',
            'username',
            'name',
            'role',
            'contact_number',
            'email',
            'address',
            'qr_code_data',
            'password',
            'must_change_credentials',
            'avatar',
            'avatar_url',
            'has_mobile_account',
            'created_at',
        ]
        read_only_fields = ['created_at', 'teacher', 'avatar_url']
    
    def get_has_mobile_account(self, obj):
        return hasattr(obj, 'mobile_account')

    def get_avatar_url(self, obj):
        """Return the Cloudinary URL directly from avatar.url if available."""
        if not obj.avatar:
            return None
        try:
            # When using Cloudinary storage, avatar.url often returns a full URL.
            # If it's already absolute (starts with http) return as-is. Otherwise
            # attempt to build an absolute URL from the request in the serializer
            # context so clients (mobile/web) can fetch the image reliably.
            url = obj.avatar.url
            if isinstance(url, str) and url.startswith('http'):
                return url

            # Try to build absolute URI if request available in context
            request = self.context.get('request') if self.context else None
            if request:
                try:
                    return request.build_absolute_uri(url)
                except Exception:
                    pass

            # Fallback: return the raw url (may be relative)
            return url
        except Exception:
            return None


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
    parent1_username = serializers.CharField(max_length=150, required=False, allow_blank=True)
    parent1_password = serializers.CharField(max_length=100, required=False, allow_blank=True)

    parent2_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    parent2_contact = serializers.CharField(max_length=15, required=False, allow_blank=True)
    parent2_email = serializers.EmailField(required=False, allow_blank=True)
    parent2_username = serializers.CharField(max_length=150, required=False, allow_blank=True)
    parent2_password = serializers.CharField(max_length=100, required=False, allow_blank=True)

    guardian_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    guardian_contact = serializers.CharField(max_length=15, required=False, allow_blank=True)
    guardian_email = serializers.EmailField(required=False, allow_blank=True)
    guardian_username = serializers.CharField(max_length=150, required=False, allow_blank=True)
    guardian_password = serializers.CharField(max_length=100, required=False, allow_blank=True)

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


class ParentNotificationSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    student_name = serializers.CharField(source='student.name', read_only=True)
    student_lrn = serializers.CharField(source='student.lrn', read_only=True)

    class Meta:
        model = ParentNotification
        fields = [
            'id',
            'parent',
            'parent_name',
            'student',
            'student_name',
            'student_lrn',
            'type',
            'message',
            'extra_data',
            'created_at',
        ]
        read_only_fields = ['created_at']

    def create(self, validated_data):
        if not validated_data.get('student'):
            validated_data['student'] = validated_data['parent'].student
        return super().create(validated_data)


class ParentEventSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.user.username', read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True, allow_null=True)
    student_name = serializers.CharField(source='student.name', read_only=True, allow_null=True)
    student_lrn = serializers.CharField(source='student.lrn', read_only=True, allow_null=True)
    section = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = ParentEvent
        fields = [
            'id',
            'teacher',
            'teacher_name',
            'parent',
            'parent_name',
            'student',
            'student_name',
            'student_lrn',
            'section',
            'title',
            'description',
            'event_type',
            'scheduled_at',
            'location',
            'extra_data',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'teacher']
        extra_kwargs = {
            'parent': {'required': False, 'allow_null': True},
            'student': {'required': False, 'allow_null': True}
        }


class ParentScheduleSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    student_name = serializers.CharField(source='student.name', read_only=True)
    student_lrn = serializers.CharField(source='student.lrn', read_only=True)
    teacher_name = serializers.CharField(source='teacher.user.username', read_only=True, default=None)

    class Meta:
        model = ParentSchedule
        fields = [
            'id',
            'parent',
            'parent_name',
            'student',
            'student_name',
            'student_lrn',
            'teacher',
            'teacher_name',
            'subject',
            'description',
            'day_of_week',
            'start_time',
            'end_time',
            'time_label',
            'room',
            'icon',
            'extra_data',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, data):
        parent = data.get('parent')
        student = data.get('student')
        if not parent and not student:
            raise serializers.ValidationError("Either parent or student must be provided.")
        if parent and student and parent.student != student:
            raise serializers.ValidationError("Provided student does not match the parent's student.")
        return data

    def create(self, validated_data):
        validated_data = self._attach_relationship_defaults(validated_data)
        validated_data = self._ensure_time_label(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = self._attach_relationship_defaults(validated_data, fallback_instance=instance)
        validated_data = self._ensure_time_label(validated_data, fallback_instance=instance)
        return super().update(instance, validated_data)

    def _attach_relationship_defaults(self, data, fallback_instance=None):
        parent = data.get('parent') or getattr(fallback_instance, 'parent', None)
        if parent:
            if not data.get('student'):
                data['student'] = parent.student
            if not data.get('teacher'):
                data['teacher'] = parent.teacher
        return data

    def _ensure_time_label(self, data, fallback_instance=None):
        if data.get('time_label'):
            return data
        start = data.get('start_time')
        end = data.get('end_time')
        if not start and not end and fallback_instance:
            start = getattr(fallback_instance, 'start_time', None)
            end = getattr(fallback_instance, 'end_time', None)
        label = self._build_time_label(start, end)
        if label:
            data['time_label'] = label
        return data

    def _build_time_label(self, start, end):
        def _fmt(value):
            if not value:
                return None
            return value.strftime("%I:%M %p").lstrip('0')

        start_str = _fmt(start)
        end_str = _fmt(end)
        if start_str and end_str:
            return f"{start_str} - {end_str}"
        return start_str or end_str