from django.contrib.auth import authenticate
from django.db import IntegrityError
from rest_framework import generics, permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import TeacherProfile, Attendance
from .serializers import TeacherProfileSerializer, AttendanceSerializer

# -----------------------------
# TEACHER REGISTRATION
# -----------------------------
class RegisterView(generics.CreateAPIView):
    queryset = TeacherProfile.objects.all()
    serializer_class = TeacherProfileSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            teacher_profile = serializer.save()
            token, _ = Token.objects.get_or_create(user=teacher_profile.user)
            return Response({
                "message": "Registration successful!",
                "token": token.key,
                "username": teacher_profile.user.username
            }, status=status.HTTP_201_CREATED)
        except IntegrityError:
            return Response(
                {"error": "Username already exists."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# -----------------------------
# TEACHER LOGIN
# -----------------------------
class LoginView(APIView):
    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(username=username, password=password)
        
        if user:
            token, _ = Token.objects.get_or_create(user=user)
            return Response({"token": token.key, "username": username})
        return Response({"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)

# -----------------------------
# ATTENDANCE (Authenticated)
# -----------------------------
class AttendanceView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        attendances = Attendance.objects.all().order_by('-timestamp')
        serializer = AttendanceSerializer(attendances, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request):
        serializer = AttendanceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# -----------------------------
# PUBLIC ATTENDANCE (No Auth)
# -----------------------------
class PublicAttendanceListView(generics.ListAPIView):
    queryset = Attendance.objects.all().order_by('-timestamp')
    serializer_class = AttendanceSerializer
    permission_classes = []

# -----------------------------
# GUARDIAN REGISTRATION (Using Attendance Table)
# -----------------------------
class UnregisteredGuardianView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get all unregistered guardians"""
        try:
            guardians = Attendance.objects.filter(is_unregistered=True).order_by('-timestamp')
            data = [{
                'id': g.id,
                'name': g.guardian_name,
                'age': g.guardian_age,
                'address': g.guardian_address,
                'relationship': g.guardian_relationship,
                'contact': g.guardian_contact,
                'student': g.student_name,
                'timestamp': g.timestamp.isoformat()
            } for g in guardians]
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"Error fetching guardians: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request):
        """Register a new unregistered guardian"""
        try:
            # Get the teacher profile
            try:
                teacher_profile = TeacherProfile.objects.get(user=request.user)
            except TeacherProfile.DoesNotExist:
                return Response(
                    {"error": "Teacher profile not found. Please complete your profile first."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate required fields
            required_fields = ['name', 'age', 'address', 'relationship', 'contact', 'student']
            for field in required_fields:
                if not request.data.get(field):
                    return Response(
                        {"error": f"Missing required field: {field}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Create attendance record with guardian info
            guardian = Attendance.objects.create(
                teacher=teacher_profile,
                student_name=request.data.get('student'),
                qr_code_data='UNREGISTERED_GUARDIAN',
                guardian_name=request.data.get('name'),
                guardian_age=int(request.data.get('age')),
                guardian_address=request.data.get('address'),
                guardian_relationship=request.data.get('relationship'),
                guardian_contact=request.data.get('contact'),
                is_unregistered=True
            )
            
            return Response({
                'id': guardian.id,
                'name': guardian.guardian_name,
                'age': guardian.guardian_age,
                'address': guardian.guardian_address,
                'relationship': guardian.guardian_relationship,
                'contact': guardian.guardian_contact,
                'student': guardian.student_name,
                'timestamp': guardian.timestamp.isoformat()
            }, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response(
                {"error": f"Invalid data format: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"Error creating guardian: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
