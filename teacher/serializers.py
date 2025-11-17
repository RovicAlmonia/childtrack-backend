from rest_framework import serializers
from django.contrib.auth.models import User
from .models import TeacherProfile, Attendance, Absence, Dropout, UnauthorizedPerson
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

class AttendanceViewSet(viewsets.ModelViewSet):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Attendance.objects.filter(teacher__user=self.request.user)
    
    def perform_create(self, serializer):
        teacher_profile = TeacherProfile.objects.get(user=self.request.user)
        serializer.save(teacher=teacher_profile)
    
    def perform_update(self, serializer):
        # Ensure teacher is set correctly on update
        teacher_profile = TeacherProfile.objects.get(user=self.request.user)
        serializer.save(teacher=teacher_profile)
    
    # Public endpoint for reading attendance (no auth required)
    @action(detail=False, methods=['get'], permission_classes=[AllowAny], url_path='public')
    def public_list(self, request):
        queryset = Attendance.objects.all()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)



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

