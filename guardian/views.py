from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from teacher.models import TeacherProfile
from .models import Guardian
from .serializers import GuardianSerializer

class GuardianView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get all guardians"""
        try:
            guardians = Guardian.objects.all().order_by('-timestamp')
            serializer = GuardianSerializer(guardians, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"Error fetching guardians: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request):
        """Register a new guardian"""
        try:
            # Get the teacher profile
            try:
                teacher_profile = TeacherProfile.objects.get(user=request.user)
            except TeacherProfile.DoesNotExist:
                return Response(
                    {"error": "Teacher profile not found."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Prepare data with teacher
            data = request.data.copy()
            data['teacher'] = teacher_profile.id
            
            # Validate and save
            serializer = GuardianSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response(
                {"error": f"Error creating guardian: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
