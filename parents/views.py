from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
import json
from .models import Student, ParentGuardian
from teacher.models import TeacherProfile
from .serializers import (
    StudentSerializer, 
    ParentGuardianSerializer, 
    RegistrationSerializer,
    TeacherStudentsSerializer
)

class StudentRegistrationView(APIView):
    """
    Register student with parents/guardians under a specific teacher
    Requires authentication
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        try:
            # Get teacher (can be from authenticated user or specified teacher_id)
            teacher_id = data.get('teacher_id')
            try:
                # If teacher_id is provided, use it (for admin/teacher registering students)
                if teacher_id:
                    teacher = TeacherProfile.objects.get(id=teacher_id)
                else:
                    # Otherwise use authenticated user's teacher profile
                    teacher = TeacherProfile.objects.get(user=request.user)
            except TeacherProfile.DoesNotExist:
                return Response(
                    {'error': 'Teacher profile not found'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            with transaction.atomic():
                # Create or update student
                student, created = Student.objects.update_or_create(
                    lrn=data['lrn'],
                    defaults={
                        'name': data['student_name'],
                        'grade_level': data.get('grade_level', ''),
                        'section': data.get('section', ''),
                        'teacher': teacher  # ✅ Link to teacher
                    }
                )
                
                # Delete existing parent/guardian records for this student
                ParentGuardian.objects.filter(student=student).delete()
                
                # Create parent/guardian records with QR data
                parents_data = [
                    {
                        'role': 'Parent1',
                        'name': data['parent1_name'],
                        'contact': data.get('parent1_contact', ''),
                        'email': data.get('parent1_email', ''),
                    },
                    {
                        'role': 'Parent2',
                        'name': data['parent2_name'],
                        'contact': data.get('parent2_contact', ''),
                        'email': data.get('parent2_email', ''),
                    },
                    {
                        'role': 'Guardian',
                        'name': data['guardian_name'],
                        'contact': data.get('guardian_contact', ''),
                        'email': data.get('guardian_email', ''),
                    }
                ]
                
                created_records = []
                for parent_data in parents_data:
                    # Generate QR code payload
                    qr_payload = {
                        'lrn': student.lrn,
                        'student': student.name,
                        'role': parent_data['role'],
                        'name': parent_data['name']
                    }
                    
                    parent_guardian = ParentGuardian.objects.create(
                        student=student,
                        teacher=teacher,  # ✅ Link to teacher
                        name=parent_data['name'],
                        role=parent_data['role'],
                        contact_number=parent_data['contact'],
                        email=parent_data['email'],
                        address=data.get('address', ''),
                        qr_code_data=json.dumps(qr_payload)
                    )
                    created_records.append(parent_guardian)
                
                # Prepare response
                response_data = {
                    'message': 'Registration successful!',
                    'student': {
                        'lrn': student.lrn,
                        'name': student.name,
                        'grade_level': student.grade_level,
                        'section': student.section,
                        'teacher': teacher.user.username,
                    },
                    'qr_codes': []
                }
                
                for pg in created_records:
                    response_data['qr_codes'].append({
                        'id': pg.id,
                        'role': pg.role,
                        'name': pg.name,
                        'qr_data': json.loads(pg.qr_code_data)
                    })
                
                return Response(response_data, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response(
                {'error': f'Registration failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TeacherStudentsView(APIView):
    """
    Get all students and their parents/guardians for the authenticated teacher
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            teacher = TeacherProfile.objects.get(user=request.user)
            serializer = TeacherStudentsSerializer(teacher)
            return Response(serializer.data)
        except TeacherProfile.DoesNotExist:
            return Response(
                {'error': 'Teacher profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )

class StudentListView(APIView):
    """Get all students for authenticated teacher or all students (admin)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            # If user is teacher, show only their students
            teacher = TeacherProfile.objects.get(user=request.user)
            students = Student.objects.filter(teacher=teacher)
        except TeacherProfile.DoesNotExist:
            # If not teacher (admin), show all students
            students = Student.objects.all()
        
        serializer = StudentSerializer(students, many=True)
        return Response(serializer.data)

class ParentGuardianListView(APIView):
    """Get all parents/guardians for authenticated teacher"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, lrn=None):
        try:
            teacher = TeacherProfile.objects.get(user=request.user)
            
            if lrn:
                # Get parents for specific student under this teacher
                parents = ParentGuardian.objects.filter(
                    teacher=teacher,
                    student__lrn=lrn
                )
            else:
                # Get all parents for this teacher
                parents = ParentGuardian.objects.filter(teacher=teacher)
            
            serializer = ParentGuardianSerializer(parents, many=True)
            return Response(serializer.data)
        except TeacherProfile.DoesNotExist:
            return Response(
                {'error': 'Teacher profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )

class StudentDetailView(APIView):
    """Get student details with all parents/guardians"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, lrn):
        try:
            teacher = TeacherProfile.objects.get(user=request.user)
            student = Student.objects.get(lrn=lrn, teacher=teacher)
            parents = ParentGuardian.objects.filter(student=student)
            
            response_data = {
                'student': StudentSerializer(student).data,
                'parents_guardians': ParentGuardianSerializer(parents, many=True).data
            }
            
            return Response(response_data)
        except TeacherProfile.DoesNotExist:
            return Response(
                {'error': 'Teacher profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Student.DoesNotExist:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )

class AllTeachersStudentsView(APIView):
    """
    Admin view - Get all teachers with their students and parents/guardians
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        teachers = TeacherProfile.objects.all()
        serializer = TeacherStudentsSerializer(teachers, many=True)
        return Response(serializer.data)
