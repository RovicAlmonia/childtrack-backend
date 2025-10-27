from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
import json
from .models import Student, ParentGuardian
from .serializers import StudentSerializer, ParentGuardianSerializer, RegistrationSerializer

class StudentRegistrationView(APIView):
    """
    Public endpoint for parent/guardian registration
    Creates student and all associated parents/guardians with QR codes
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    
    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        try:
            with transaction.atomic():
                # Create or update student
                student, created = Student.objects.update_or_create(
                    lrn=data['lrn'],
                    defaults={
                        'name': data['student_name'],
                        'grade_level': data.get('grade_level', ''),
                        'section': data.get('section', ''),
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

class StudentListView(APIView):
    """Get all registered students"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        students = Student.objects.all()
        serializer = StudentSerializer(students, many=True)
        return Response(serializer.data)

class ParentGuardianListView(APIView):
    """Get all parents/guardians for a specific student"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, lrn=None):
        if lrn:
            parents = ParentGuardian.objects.filter(student__lrn=lrn)
        else:
            parents = ParentGuardian.objects.all()
        
        serializer = ParentGuardianSerializer(parents, many=True)
        return Response(serializer.data)

class StudentDetailView(APIView):
    """Get student details with all parents/guardians"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, lrn):
        try:
            student = Student.objects.get(lrn=lrn)
            parents = ParentGuardian.objects.filter(student=student)
            
            response_data = {
                'student': StudentSerializer(student).data,
                'parents_guardians': ParentGuardianSerializer(parents, many=True).data
            }
            
            return Response(response_data)
        except Student.DoesNotExist:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )
