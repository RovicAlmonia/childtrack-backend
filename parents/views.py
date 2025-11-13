import logging
import json
from django.db import transaction
from django.db.models import Prefetch
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from .models import Student, ParentGuardian
from teacher.models import TeacherProfile
from .serializers import (
    StudentSerializer,
    ParentGuardianSerializer,
    RegistrationSerializer,
    TeacherStudentsSerializer
)

logger = logging.getLogger(__name__)

import traceback


class StandardPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 100


def _perform_registration(data, request_user=None):
    """
    Internal helper that performs the registration and returns (student, created_records, created_flag)
    Raises exceptions if something goes wrong.
    """
    # Resolve teacher: prefer provided teacher_id, else from request_user if available
    teacher = None
    teacher_id = data.get("teacher_id")
    if teacher_id:
        try:
            teacher = TeacherProfile.objects.get(id=teacher_id)
        except TeacherProfile.DoesNotExist:
            raise ValueError("Teacher profile not found for provided teacher_id.")
    else:
        if request_user is None:
            raise ValueError("teacher_id is required for public registrations.")
        try:
            teacher = TeacherProfile.objects.get(user=request_user)
        except TeacherProfile.DoesNotExist:
            raise ValueError("Teacher profile not found for authenticated user.")

    # Create or update student
    student, created = Student.objects.update_or_create(
        lrn=data["lrn"],
        defaults={
            "name": data["student_name"],
            "gender": data.get("gender", ""),
            "grade_level": data.get("grade_level", ""),
            "section": data.get("section", ""),
            "teacher": teacher,
        },
    )

    # Remove existing parents for this student (we recreate)
    ParentGuardian.objects.filter(student=student).delete()

    parents_data = []
    # Only append parents that have a name (serializer validated at least 1)
    if data.get("parent1_name"):
        parents_data.append(
            {
                "role": "Parent1",
                "name": data["parent1_name"],
                "contact": data.get("parent1_contact", ""),
                "email": data.get("parent1_email", ""),
            }
        )
    if data.get("parent2_name"):
        parents_data.append(
            {
                "role": "Parent2",
                "name": data["parent2_name"],
                "contact": data.get("parent2_contact", ""),
                "email": data.get("parent2_email", ""),
            }
        )
    if data.get("guardian_name"):
        parents_data.append(
            {
                "role": "Guardian",
                "name": data["guardian_name"],
                "contact": data.get("guardian_contact", ""),
                "email": data.get("guardian_email", ""),
            }
        )

    created_records = []
    for parent_data in parents_data:
        qr_payload = {
            "lrn": student.lrn,
            "student": student.name,
            "gender": student.gender,
            "role": parent_data["role"],
            "name": parent_data["name"],
        }

        pg = ParentGuardian.objects.create(
            student=student,
            teacher=teacher,
            name=parent_data["name"],
            role=parent_data["role"],
            contact_number=parent_data["contact"],
            email=parent_data["email"],
            address=data.get("address", ""),
            qr_code_data=json.dumps(qr_payload),
        )
        created_records.append(pg)

    return student, created_records, created


class RegistrationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            print("🔹 Incoming data:", json.dumps(request.data, indent=2))
            serializer = RegistrationSerializer(data=request.data)
            if serializer.is_valid():
                result = serializer.save()
                return Response(result, status=status.HTTP_201_CREATED)
            print("❌ Serializer errors:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print("❌ SERVER ERROR:", e)
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AuthenticatedStudentRegistrationView(APIView):
    """
    Authenticated registration endpoint: /api/parents/register/
    Teacher must be authenticated. teacher_id is optional (will use authenticated teacher if omitted).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = serializer.validated_data
            with transaction.atomic():
                student, created_records, created_flag = _perform_registration(data, request_user=request.user)

            response = {
                "message": "Registration successful!",
                "status": "created" if created_flag else "updated",
                "student": StudentSerializer(student).data,
                "parents_guardians": ParentGuardianSerializer(created_records, many=True).data,
            }
            return Response(response, status=status.HTTP_201_CREATED if created_flag else status.HTTP_200_OK)
        except ValueError as ve:
            logger.warning("Registration validation/lookup error: %s", str(ve))
            return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("Registration failed")
            return Response({"error": f"Registration failed: {str(exc)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PublicStudentRegistrationView(APIView):
    """
    Public registration endpoint: /api/parents/public/register/
    Allows non-authenticated registration but REQUIRES teacher_id in payload.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = serializer.validated_data
            # For public route, require teacher_id
            if not data.get("teacher_id"):
                return Response({"error": "teacher_id is required for public registration."}, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                student, created_records, created_flag = _perform_registration(data, request_user=None)

            response = {
                "message": "Registration successful!",
                "status": "created" if created_flag else "updated",
                "student": StudentSerializer(student).data,
                "parents_guardians": ParentGuardianSerializer(created_records, many=True).data,
            }
            return Response(response, status=status.HTTP_201_CREATED if created_flag else status.HTTP_200_OK)
        except ValueError as ve:
            logger.warning("Public registration validation error: %s", str(ve))
            return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("Public registration failed")
            return Response({"error": f"Registration failed: {str(exc)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TeacherStudentsView(APIView):
    """
    Get all students and their parents/guardians for the authenticated teacher
    Endpoint: /api/parents/teacher-students/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            teacher = TeacherProfile.objects.get(user=request.user)
        except TeacherProfile.DoesNotExist:
            return Response({"error": "Teacher profile not found"}, status=status.HTTP_404_NOT_FOUND)

        # Prefetch parents for students to avoid N+1
        students_qs = teacher.students.prefetch_related('parents_guardians')
        serializer = TeacherStudentsSerializer(teacher)
        return Response(serializer.data)


class StudentListView(APIView):
    """
    List students for the authenticated teacher (paginated).
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get(self, request):
        try:
            teacher = TeacherProfile.objects.get(user=request.user)
            qs = Student.objects.filter(teacher=teacher).prefetch_related('parents_guardians')
        except TeacherProfile.DoesNotExist:
            # Admin fallback: return all students
            qs = Student.objects.all().prefetch_related('parents_guardians')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = StudentSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ParentGuardianListView(APIView):
    """
    Get parents/guardians for authenticated teacher, optionally filtered by LRN (paginated).
    /api/parents/parents/?lrn=<lrn>
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get(self, request):
        lrn = request.query_params.get('lrn')
        try:
            teacher = TeacherProfile.objects.get(user=request.user)
        except TeacherProfile.DoesNotExist:
            return Response({"error": "Teacher profile not found"}, status=status.HTTP_404_NOT_FOUND)

        if lrn:
            qs = ParentGuardian.objects.filter(teacher=teacher, student__lrn=lrn)
        else:
            qs = ParentGuardian.objects.filter(teacher=teacher)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = ParentGuardianSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class StudentDetailView(APIView):
    """
    Get details for a single student (must belong to authenticated teacher).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, lrn):
        try:
            teacher = TeacherProfile.objects.get(user=request.user)
            student = Student.objects.get(lrn=lrn, teacher=teacher)
        except TeacherProfile.DoesNotExist:
            return Response({"error": "Teacher profile not found"}, status=status.HTTP_404_NOT_FOUND)
        except Student.DoesNotExist:
            return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

        parents = ParentGuardian.objects.filter(student=student)
        response_data = {
            "student": StudentSerializer(student).data,
            "parents_guardians": ParentGuardianSerializer(parents, many=True).data,
        }
        return Response(response_data)


class AllTeachersStudentsView(APIView):
    """
    Admin view: return all teachers with their students (prefetched).
    """
    permission_classes = [permissions.IsAuthenticated]  # you can restrict further (admin-only)

    def get(self, request):
        teachers = TeacherProfile.objects.prefetch_related(
            Prefetch('students', queryset=Student.objects.prefetch_related('parents_guardians')),
            'parents_guardians'  # if needed
        )
        serializer = TeacherStudentsSerializer(teachers, many=True)
        return Response(serializer.data)
