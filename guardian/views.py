
# ==========================================
# views.py - Updated Guardian View
# ==========================================
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from teacher.models import TeacherProfile
from .models import Guardian
from .serializers import GuardianSerializer
import base64
from django.core.files.base import ContentFile

class GuardianView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]  # Support file uploads
    
    def get(self, request):
        """Get all guardians"""
        try:
            guardians = Guardian.objects.all().order_by('-timestamp')
            serializer = GuardianSerializer(guardians, many=True, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
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
            
            # Check for direct file upload
            elif 'photo' in request.FILES:
                data['photo'] = request.FILES['photo']
            
            # Validate and save
            serializer = GuardianSerializer(data=data, context={'request': request})
            if serializer.is_valid():
                guardian = serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
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
                'contact': required_fields['contact'],
                'student_name': required_fields['student_name']
            }
            
            # Validate and save
            serializer = GuardianSerializer(data=data)
            if serializer.is_valid():
                guardian = serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
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
