from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from teacher.models import TeacherProfile
from .models import Guardian
from .serializers import GuardianSerializer
import base64
from django.core.files.base import ContentFile
from django.db.models import Q

class GuardianView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get(self, request, pk=None):
        """Get all guardians for the authenticated teacher or by teacher ID"""
        try:
      
            if pk:
                try:
                    teacher_profile = TeacherProfile.objects.get(id=pk)
                except TeacherProfile.DoesNotExist:
                    return Response(
                        {"error": "Teacher profile not found."},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                # Get guardians for authenticated teacher
                try:
                    teacher_profile = TeacherProfile.objects.get(user=request.user)
                except TeacherProfile.DoesNotExist:
                    return Response(
                        {"error": "Teacher profile not found."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Get guardians for this teacher
            guardians = Guardian.objects.filter(teacher=teacher_profile).order_by('-timestamp')
            serializer = GuardianSerializer(guardians, many=True, context={'request': request})
            
            return Response({
                "count": guardians.count(),
                "teacher_id": teacher_profile.id,
                "teacher_name": teacher_profile.user.get_full_name() or teacher_profile.user.username,
                "results": serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": f"Error fetching guardians: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request):
        """Register a new guardian with optional photo"""
        try:
            # Get the teacher profile
            try:
                teacher_profile = TeacherProfile.objects.get(user=request.user)
            except TeacherProfile.DoesNotExist:
                return Response(
                    {"error": "Teacher profile not found."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Accept both 'student' and 'student_name' for flexibility
            student_name = request.data.get('student_name') or request.data.get('student')
            
            # Validate required fields
            name = request.data.get('name')
            age = request.data.get('age')
            
            if not name or not age or not student_name:
                return Response(
                    {"error": "Missing required fields: name, age, and student_name are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Prepare data with teacher
            data = {
                'teacher': teacher_profile.id,
                'name': name,
                'age': int(age),
                'address': request.data.get('address', ''),
                'relationship': request.data.get('relationship', ''),
                'contact': request.data.get('contact', ''),
                'student_name': student_name
            }
            
            # Handle photo upload (base64 or file)
            photo = None
            
            # Check for base64 photo data
            photo_base64 = request.data.get('photo_base64')
            if photo_base64:
                try:
                    # Remove data URL prefix if present
                    if 'base64,' in photo_base64:
                        photo_base64 = photo_base64.split('base64,')[1]
                    
                    # Decode base64 and create file
                    photo_data = base64.b64decode(photo_base64)
                    photo_name = f"guardian_{name.replace(' ', '_')}_{student_name.replace(' ', '_')}.jpg"
                    photo = ContentFile(photo_data, name=photo_name)
                    data['photo'] = photo
                except Exception as e:
                    print(f"Error processing base64 photo: {e}")
                    return Response(
                        {"error": f"Invalid photo data: {str(e)}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Check for direct file upload
            elif 'photo' in request.FILES:
                data['photo'] = request.FILES['photo']
            
            # Validate and save
            serializer = GuardianSerializer(data=data, context={'request': request})
            if serializer.is_valid():
                guardian = serializer.save()
                return Response({
                    "message": "Guardian registered successfully",
                    "data": serializer.data
                }, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
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
    
    def put(self, request, pk=None):
        """Update an existing guardian"""
        try:
            # Get the teacher profile
            try:
                teacher_profile = TeacherProfile.objects.get(user=request.user)
            except TeacherProfile.DoesNotExist:
                return Response(
                    {"error": "Teacher profile not found."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get the guardian
            guardian_id = pk or request.data.get('id')
            if not guardian_id:
                return Response(
                    {"error": "Guardian ID is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                guardian = Guardian.objects.get(id=guardian_id, teacher=teacher_profile)
            except Guardian.DoesNotExist:
                return Response(
                    {"error": "Guardian not found or you don't have permission to edit it"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Handle photo update
            photo_base64 = request.data.get('photo_base64')
            if photo_base64:
                try:
                    if 'base64,' in photo_base64:
                        photo_base64 = photo_base64.split('base64,')[1]
                    
                    photo_data = base64.b64decode(photo_base64)
                    photo_name = f"guardian_{request.data.get('name', guardian.name).replace(' ', '_')}.jpg"
                    photo = ContentFile(photo_data, name=photo_name)
                    request.data['photo'] = photo
                except Exception as e:
                    print(f"Error processing base64 photo: {e}")
            
            # Update guardian
            serializer = GuardianSerializer(
                guardian, 
                data=request.data, 
                partial=True, 
                context={'request': request}
            )
            
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "message": "Guardian updated successfully",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response(
                {"error": f"Error updating guardian: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request, pk=None):
        """Delete a guardian"""
        try:
            # Get the teacher profile
            try:
                teacher_profile = TeacherProfile.objects.get(user=request.user)
            except TeacherProfile.DoesNotExist:
                return Response(
                    {"error": "Teacher profile not found."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get the guardian
            guardian_id = pk or request.data.get('id')
            if not guardian_id:
                return Response(
                    {"error": "Guardian ID is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                guardian = Guardian.objects.get(id=guardian_id, teacher=teacher_profile)
            except Guardian.DoesNotExist:
                return Response(
                    {"error": "Guardian not found or you don't have permission to delete it"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            guardian.delete()
            return Response(
                {"message": "Guardian deleted successfully"},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {"error": f"Error deleting guardian: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GuardianByTeacherView(APIView):
    """Separate view to get guardians by teacher ID"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, teacher_id):
        """Get all guardians for a specific teacher by teacher ID"""
        try:
            # Get the teacher profile
            try:
                teacher_profile = TeacherProfile.objects.get(id=teacher_id)
            except TeacherProfile.DoesNotExist:
                return Response(
                    {"error": f"Teacher profile with ID {teacher_id} not found."},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get guardians for this teacher
            guardians = Guardian.objects.filter(teacher=teacher_profile).order_by('-timestamp')
            serializer = GuardianSerializer(guardians, many=True, context={'request': request})
            
            return Response({
                "count": guardians.count(),
                "teacher_id": teacher_profile.id,
                "teacher_name": teacher_profile.user.get_full_name() or teacher_profile.user.username,
                "results": serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": f"Error fetching guardians: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# new
class GuardianPublicListView(APIView):
    """
    Lightweight read-only endpoint so parents/mobile clients can view pending guardians.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        teacher_id = request.query_params.get('teacher')
        student_name = request.query_params.get('student_name')
        search = request.query_params.get('search')
        limit = request.query_params.get('limit')

        queryset = Guardian.objects.all().order_by('-timestamp')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)
        if student_name:
            queryset = queryset.filter(student_name__iexact=student_name)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(student_name__icontains=search)
                | Q(relationship__icontains=search)
            )
        if limit:
            try:
                limit_value = max(1, min(int(limit), 500))
                queryset = queryset[:limit_value]
            except (TypeError, ValueError):
                pass

        serializer = GuardianSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class GuardianByTeacherView(APIView):
    """Separate view to get guardians by teacher ID"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, teacher_id):
        """Get all guardians for a specific teacher by teacher ID"""
        try:
            # Get the teacher profile
            try:
                teacher_profile = TeacherProfile.objects.get(id=teacher_id)
            except TeacherProfile.DoesNotExist:
                return Response(
                    {"error": f"Teacher profile with ID {teacher_id} not found."},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get guardians for this teacher
            guardians = Guardian.objects.filter(teacher=teacher_profile).order_by('-timestamp')
            serializer = GuardianSerializer(guardians, many=True, context={'request': request})
            
            return Response({
                "count": guardians.count(),
                "teacher_id": teacher_profile.id,
                "teacher_name": teacher_profile.user.get_full_name() or teacher_profile.user.username,
                "results": serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": f"Error fetching guardians: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
