from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from teacher.models import TeacherProfile
from parents.models import ParentGuardian, ParentMobileAccount
from .models import Guardian
from .serializers import GuardianSerializer
from django.db.models import Q

class GuardianView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]

    def patch(self, request, pk=None, **kwargs):
        """Partially update a guardian (e.g., status change)"""
        try:
            # Extract pk from kwargs if not provided as parameter
            if pk is None and 'pk' in kwargs:
                pk = kwargs['pk']
            
            # Get the guardian
            if not pk:
                return Response(
                    {"error": "Guardian ID is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                guardian = Guardian.objects.get(id=pk)
            except Guardian.DoesNotExist:
                return Response(
                    {"error": "Guardian not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Verify user is authorized to update this guardian
            try:
                teacher_profile = TeacherProfile.objects.get(user=request.user)
                # User is a teacher, allow update if it's their guardian
                if guardian.teacher != teacher_profile:
                    return Response(
                        {"error": "You don't have permission to edit this guardian"},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except TeacherProfile.DoesNotExist:
                # User is not a teacher (likely a parent/guardian)
                # Only allow updating the status field
                if request.data and len(request.data) > 0:
                    allowed_fields = {'status'}
                    provided_fields = set(request.data.keys())
                    if not provided_fields.issubset(allowed_fields):
                        return Response(
                            {"error": "Parents/Guardians can only update the status field"},
                            status=status.HTTP_403_FORBIDDEN
                        )
            
            # Update guardian with partial data
            print(f"[PATCH DEBUG] Updating guardian {pk} with data: {request.data}")
            serializer = GuardianSerializer(
                guardian, 
                data=request.data, 
                partial=True,
                context={'request': request}
            )
            
            if serializer.is_valid():
                updated_guardian = serializer.save()
                print(f"[PATCH DEBUG] Guardian {pk} updated successfully. New status: {updated_guardian.status}")
                return Response({
                    "message": "Guardian updated successfully",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
            
            print(f"[PATCH DEBUG] Serializer errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response(
                {"error": f"Error updating guardian: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get(self, request, pk=None, **kwargs):
        """Get all guardians for the authenticated teacher or by teacher ID"""
        try:
            # Extract pk from kwargs if not provided as parameter
            if pk is None and 'pk' in kwargs:
                pk = kwargs['pk']
            
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
        """Register a new guardian with base64 photo"""
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
            
            # Handle base64 photo if provided
            photo_base64 = request.data.get('photo_base64')
            if photo_base64:
                data['photo_base64'] = photo_base64
            
            # Validate and save
            serializer = GuardianSerializer(data=data, context={'request': request})
            if serializer.is_valid():
                guardian = serializer.save()
                # best-effort: notify parents via server push
                try:
                    from devices.expo import notify_parents_of_guardian
                    try:
                        notify_parents_of_guardian(guardian)
                    except Exception:
                        pass
                except Exception:
                    pass
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
    
    def put(self, request, pk=None, **kwargs):
        """Update an existing guardian"""
        try:
            # Extract pk from kwargs if not provided as parameter
            if pk is None and 'pk' in kwargs:
                pk = kwargs['pk']
            
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
            
            # Update guardian (photo_base64 will be handled by serializer)
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
    
    def delete(self, request, pk=None, **kwargs):
        """Delete a guardian"""
        try:
            # Extract pk from kwargs if not provided as parameter
            if pk is None and 'pk' in kwargs:
                pk = kwargs['pk']
            
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


class ParentGuardianListView(APIView):
    """
    Endpoint for parents to view and manage guardian requests for their child.
    Parents pass their parent_id as query parameter.
    """
    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser]

    def get(self, request):
        """Get all pending guardians for a parent's child"""
        try:
            # Get parent_id from query parameter
            parent_id = request.query_params.get('parent_id')
            
            if not parent_id:
                return Response(
                    {"error": "parent_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                parent_guardian = ParentGuardian.objects.get(id=parent_id)
            except ParentGuardian.DoesNotExist:
                return Response(
                    {"error": "Parent guardian account not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get guardians for this parent's student
            student = parent_guardian.student
            guardians = Guardian.objects.filter(
                (Q(student=student) | Q(student_name__iexact=student.name)),
                status='pending'
            ).order_by('-timestamp')
            
            serializer = GuardianSerializer(guardians, many=True, context={'request': request})
            
            return Response({
                "count": guardians.count(),
                "student_id": student.lrn,
                "student_name": student.name,
                "results": serializer.data
            }, status=status.HTTP_200_OK)
            
        except ParentGuardian.DoesNotExist:
            return Response(
                {"error": "Parent guardian account not found"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"Error fetching guardians: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def patch(self, request, pk=None):
        """Update guardian status (allow/decline) for parent"""
        try:
            if not pk:
                return Response(
                    {"error": "Guardian ID is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get parent_id from query parameter
            parent_id = request.query_params.get('parent_id')
            
            if not parent_id:
                return Response(
                    {"error": "parent_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                parent_guardian = ParentGuardian.objects.get(id=parent_id)
            except ParentGuardian.DoesNotExist:
                return Response(
                    {"error": "Parent guardian account not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get the guardian - verify it belongs to this parent's student
            guardian_qs = Guardian.objects.filter(id=pk).filter(
                Q(student=parent_guardian.student) | Q(student_name__iexact=parent_guardian.student.name)
            )
            guardian = guardian_qs.first()
            if not guardian:
                return Response(
                    {"error": "Guardian not found or does not belong to your child"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Only allow updating status field for parents
            allowed_fields = {'status'}
            provided_fields = set(request.data.keys())
            if not provided_fields.issubset(allowed_fields):
                return Response(
                    {"error": "Parents can only update the status field"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Update status
            serializer = GuardianSerializer(
                guardian,
                data=request.data,
                partial=True,
                context={'request': request}
            )
            
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "message": "Guardian status updated successfully",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response(
                {"error": f"Error updating guardian: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, pk=None):
        """Delete a guardian for parent"""
        try:
            if not pk:
                return Response(
                    {"error": "Guardian ID is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get parent_id from query parameter
            parent_id = request.query_params.get('parent_id')
            
            if not parent_id:
                return Response(
                    {"error": "parent_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get the parent guardian account
            parent_guardian = None
            try:
                parent_guardian = ParentGuardian.objects.get(id=parent_id)
            except ParentGuardian.DoesNotExist:
                return Response(
                    {"error": "Parent guardian account not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            if not parent_guardian:
                return Response(
                    {"error": "Parent guardian account not found"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get the guardian - verify it belongs to this parent's student
            guardian_qs = Guardian.objects.filter(id=pk).filter(
                Q(student=parent_guardian.student) | Q(student_name__iexact=parent_guardian.student.name)
            )
            guardian = guardian_qs.first()
            if not guardian:
                return Response(
                    {"error": "Guardian not found or does not belong to your child"},
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
