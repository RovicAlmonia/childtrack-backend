from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django.db.models import Count, Q
import json
from teacher.models import TeacherProfile
from .models import Student, ParentGuardian
from .serializers import (
    StudentSerializer, 
    ParentGuardianSerializer, 
    RegistrationSerializer,
    StudentDetailSerializer
)

class StudentRegistrationView(APIView):
    """
    Authenticated endpoint for teacher to register students with parents/guardians
    Creates student and all associated parents/guardians with QR codes
    All records are linked to the authenticated teacher
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Get teacher profile
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
        except TeacherProfile.DoesNotExist:
            return Response(
                {'error': 'Teacher profile not found. Please complete your profile first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # Check if student already exists under another teacher
                existing_student = Student.objects.filter(lrn=data['lrn']).first()
                if existing_student and existing_student.teacher != teacher_profile:
                    return Response(
                        {'error': f'Student with LRN {data["lrn"]} is already registered under another teacher.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Create or update student (linked to teacher)
                student, created = Student.objects.update_or_create(
                    lrn=data['lrn'],
                    defaults={
                        'name': data['student_name'],
                        'grade_level': data.get('grade_level', ''),
                        'section': data.get('section', ''),
                        'teacher': teacher_profile  # ✅ Link to teacher
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
                        'name': parent_data['name'],
                        'teacher': teacher_profile.user.username
                    }
                    
                    parent_guardian = ParentGuardian.objects.create(
                        student=student,
                        teacher=teacher_profile,  # ✅ Link to teacher
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
                    'message': 'Registration successful!' if created else 'Student updated successfully!',
                    'student': {
                        'lrn': student.lrn,
                        'name': student.name,
                        'grade_level': student.grade_level,
                        'section': student.section,
                        'teacher': teacher_profile.user.username,
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

class MyStudentsView(APIView):
    """Get all students registered by the authenticated teacher"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            students = Student.objects.filter(teacher=teacher_profile).order_by('name')
            serializer = StudentDetailSerializer(students, many=True)
            
            return Response({
                'teacher': {
                    'username': teacher_profile.user.username,
                    'section': teacher_profile.section,
                },
                'total_students': students.count(),
                'students': serializer.data
            })
        except TeacherProfile.DoesNotExist:
            return Response(
                {'error': 'Teacher profile not found'},
                status=status.HTTP_400_BAD_REQUEST
            )

class MyParentsGuardiansView(APIView):
    """Get all parents/guardians for the authenticated teacher's students"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            parents = ParentGuardian.objects.filter(teacher=teacher_profile).order_by('student__name', 'role')
            serializer = ParentGuardianSerializer(parents, many=True)
            
            return Response({
                'teacher': {
                    'username': teacher_profile.user.username,
                    'section': teacher_profile.section,
                },
                'total_parents_guardians': parents.count(),
                'parents_guardians': serializer.data
            })
        except TeacherProfile.DoesNotExist:
            return Response(
                {'error': 'Teacher profile not found'},
                status=status.HTTP_400_BAD_REQUEST
            )

class TeacherDashboardStatsView(APIView):
    """Get statistics for teacher dashboard"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            
            students_count = Student.objects.filter(teacher=teacher_profile).count()
            parents_guardians_count = ParentGuardian.objects.filter(teacher=teacher_profile).count()
            
            # Get recent registrations
            recent_students = Student.objects.filter(teacher=teacher_profile).order_by('-created_at')[:5]
            
            return Response({
                'teacher': {
                    'username': teacher_profile.user.username,
                    'section': teacher_profile.section,
                    'contact': teacher_profile.contact,
                },
                'statistics': {
                    'total_students': students_count,
                    'total_parents_guardians': parents_guardians_count,
                    'average_per_student': round(parents_guardians_count / students_count, 1) if students_count > 0 else 0,
                },
                'recent_students': StudentSerializer(recent_students, many=True).data
            })
        except TeacherProfile.DoesNotExist:
            return Response(
                {'error': 'Teacher profile not found'},
                status=status.HTTP_400_BAD_REQUEST
            )

class StudentDetailView(APIView):
    """Get student details with all parents/guardians (teacher can only view their own students)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, lrn):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            student = Student.objects.get(lrn=lrn, teacher=teacher_profile)
            
            serializer = StudentDetailSerializer(student)
            return Response(serializer.data)
            
        except TeacherProfile.DoesNotExist:
            return Response(
                {'error': 'Teacher profile not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Student.DoesNotExist:
            return Response(
                {'error': 'Student not found or not under your supervision'},
                status=status.HTTP_404_NOT_FOUND
            )

# ✅ PUBLIC ENDPOINT FOR REGISTRATION PAGE (No authentication)
class PublicStudentRegistrationView(APIView):
    """
    Public endpoint for parent/guardian self-registration
    Requires teacher_id to link to a specific teacher
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    
    def post(self, request):
        # Require teacher_id in request
        teacher_id = request.data.get('teacher_id')
        if not teacher_id:
            return Response(
                {'error': 'teacher_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            teacher_profile = TeacherProfile.objects.get(id=teacher_id)
        except TeacherProfile.DoesNotExist:
            return Response(
                {'error': 'Invalid teacher_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = RegistrationSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        try:
            with transaction.atomic():
                # Check if student already exists
                existing_student = Student.objects.filter(lrn=data['lrn']).first()
                if existing_student:
                    return Response(
                        {'error': f'Student with LRN {data["lrn"]} is already registered.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Create student
                student = Student.objects.create(
                    lrn=data['lrn'],
                    name=data['student_name'],
                    grade_level=data.get('grade_level', ''),
                    section=data.get('section', ''),
                    teacher=teacher_profile
                )
                
                # Create parent/guardian records
                parents_data = [
                    {'role': 'Parent1', 'name': data['parent1_name'], 
                     'contact': data.get('parent1_contact', ''), 'email': data.get('parent1_email', '')},
                    {'role': 'Parent2', 'name': data['parent2_name'], 
                     'contact': data.get('parent2_contact', ''), 'email': data.get('parent2_email', '')},
                    {'role': 'Guardian', 'name': data['guardian_name'], 
                     'contact': data.get('guardian_contact', ''), 'email': data.get('guardian_email', '')}
                ]
                
                created_records = []
                for parent_data in parents_data:
                    qr_payload = {
                        'lrn': student.lrn,
                        'student': student.name,
                        'role': parent_data['role'],
                        'name': parent_data['name'],
                        'teacher': teacher_profile.user.username
                    }
                    
                    pg = ParentGuardian.objects.create(
                        student=student,
                        teacher=teacher_profile,
                        name=parent_data['name'],
                        role=parent_data['role'],
                        contact_number=parent_data['contact'],
                        email=parent_data['email'],
                        address=data.get('address', ''),
                        qr_code_data=json.dumps(qr_payload)
                    )
                    created_records.append(pg)
                
                response_data = {
                    'message': 'Registration successful!',
                    'student': {
                        'lrn': student.lrn,
                        'name': student.name,
                        'teacher': teacher_profile.user.username,
                    },
                    'qr_codes': [
                        {
                            'id': pg.id,
                            'role': pg.role,
                            'name': pg.name,
                            'qr_data': json.loads(pg.qr_code_data)
                        } for pg in created_records
                    ]
                }
                
                return Response(response_data, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response(
                {'error': f'Registration failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
