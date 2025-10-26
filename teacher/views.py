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
# CUSTOM ERROR HANDLER
# -----------------------------
def custom_error_handler(exc, context):
    from rest_framework.views import exception_handler
    response = exception_handler(exc, context)
    
    if response is not None:
        response.data['status_code'] = response.status_code
    else:
        # Handle non-DRF exceptions
        response = Response(
            {"error": "Internal Server Error", "details": str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    return response
