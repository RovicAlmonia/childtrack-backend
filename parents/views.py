import logging
import json
from django.db import transaction
from django.db.models import Prefetch
from django.contrib.auth import authenticate
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.authtoken.models import Token

#new
from django.utils import timezone
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import Student, ParentGuardian, ParentMobileAccount, ParentNotification, ParentEvent, ParentSchedule

from teacher.models import TeacherProfile
from .serializers import (
    StudentSerializer,
    ParentGuardianSerializer,
    RegistrationSerializer,
    TeacherStudentsSerializer,
    ParentMobileAccountSerializer,
    ParentMobileRegistrationSerializer,
    ParentMobileLoginSerializer,
    #new
    ParentNotificationSerializer,
    ParentEventSerializer,
    ParentScheduleSerializer,
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
                #new
                "username": data.get("parent1_username", ""),
                "password": data.get("parent1_password", ""),
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
            #new
            username=parent_data.get("username", ""),
            password=parent_data.get("password", ""),
            
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

     def get(self, request, pk):
        try:
            parent = ParentGuardian.objects.get(pk=pk)
        except ParentGuardian.DoesNotExist:
            return Response({'error': 'Parent not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ParentGuardianSerializer(parent, context={'request': request})
        return Response(serializer.data)

    def patch(self, request, pk):
        try:
            parent = ParentGuardian.objects.get(pk=pk)
        except ParentGuardian.DoesNotExist:
            return Response({'error': 'Parent not found'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data

        logger.debug('ParentDetailView.patch called; request.FILES keys: %s', list(getattr(request, 'FILES', {}).keys()))

        # Accept both JSON and multipart form-data. Update known fields only.
        updated = False
        # capture originals to decide if must_change_credentials can be cleared
        orig_username = parent.username
        orig_password = parent.password
        orig_must = getattr(parent, 'must_change_credentials', False)

        # Handle password change explicitly: require current_password match
        changed_password = False
        # request.data may be a QueryDict (not a plain dict), so don't rely on isinstance(data, dict)
        if 'password' in data:
            new_pw = data.get('password')
            current_pw = data.get('current_password')
            # If this parent record is flagged as requiring credential change on first login,
            # allow changing the password without providing the current_password. This supports
            # the mobile first-login flow where temporary credentials were auto-generated.
            if orig_must:
                parent.password = str(new_pw)
                updated = True
                changed_password = True
            else:
                if not current_pw:
                    return Response({'error': 'current_password is required to change password.'}, status=status.HTTP_400_BAD_REQUEST)
                # simple plain-text compare (project currently stores plain passwords)
                if (parent.password or '') != str(current_pw):
                    return Response({'error': 'Current password is incorrect.'}, status=status.HTTP_401_UNAUTHORIZED)
                parent.password = str(new_pw)
                updated = True
                changed_password = True

        changed_username = False
        for field in ('name', 'username', 'contact_number', 'address', 'email'):
            if field in data:
                # track username change
                if field == 'username':
                    new_un = data.get('username')
                    if new_un is not None and str(new_un) != (orig_username or ''):
                        changed_username = True
                setattr(parent, field, data.get(field))
                updated = True

        # handle avatar upload from multipart/form-data
        if getattr(request, 'FILES', None) and 'avatar' in request.FILES:
            uploaded = request.FILES['avatar']
            logger.debug('Saving uploaded avatar file: %s (size=%s)', uploaded.name, getattr(uploaded, 'size', 'unknown'))
            print(f"[ParentDetailView] received avatar file: {uploaded.name}, size={getattr(uploaded, 'size', 'unknown')}")
            parent.avatar = uploaded
            updated = True

        if updated:
            # If parent was flagged to change credentials on first login, and the request
            # includes both a username change and a password change, clear that flag.
            if orig_must and changed_username and changed_password:
                parent.must_change_credentials = False
            parent.save()
            # debug after save
            try:
                avatar_name = parent.avatar.name
                avatar_path = getattr(parent.avatar, 'path', None)
            except Exception:
                avatar_name = None
                avatar_path = None
            logger.debug('Parent saved. avatar.name=%s avatar.path=%s', avatar_name, avatar_path)
            print(f"[ParentDetailView] parent.save() completed. avatar.name={avatar_name} avatar.path={avatar_path}")
        serializer = ParentGuardianSerializer(parent, context={'request': request})
        debug_info = {'updated': updated, 'avatar_name': avatar_name if updated else None, 'avatar_path': avatar_path if updated else None}
        # Return serializer data at top-level (keeps previous client expectations) and include debug info
        response_data = dict(serializer.data)
        response_data['debug'] = debug_info
        return Response(response_data)



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
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        teachers = TeacherProfile.objects.prefetch_related(
            Prefetch('students', queryset=Student.objects.prefetch_related('parents_guardians')),
            'parents_guardians'
        )
        serializer = TeacherStudentsSerializer(teachers, many=True)
        return Response(serializer.data)


class ParentMobileRegistrationView(APIView):
    """
    Register a parent/guardian for mobile app access
    Endpoint: /api/parents/mobile/register/
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ParentMobileRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                mobile_account = serializer.save()
                
                # Generate auth token
                token, created = Token.objects.get_or_create(user=mobile_account.user)
                
                response_data = {
                    "message": "Mobile account created successfully!",
                    "account": ParentMobileAccountSerializer(mobile_account).data,
                    "token": token.key
                }
                return Response(response_data, status=status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("Mobile registration failed")
            return Response({"error": f"Registration failed: {str(exc)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ParentMobileLoginView(APIView):
    """
    Login endpoint for parent mobile app
    Endpoint: /api/parents/mobile/login/
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ParentMobileLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        user = authenticate(username=username, password=password)
        
        if user is None:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        # Check if user has a parent mobile account
        try:
            mobile_account = ParentMobileAccount.objects.get(user=user)
            if not mobile_account.is_active:
                return Response({"error": "Account is inactive"}, status=status.HTTP_403_FORBIDDEN)
        except ParentMobileAccount.DoesNotExist:
            return Response({"error": "Not a parent mobile account"}, status=status.HTTP_403_FORBIDDEN)

        # Get or create token
        token, created = Token.objects.get_or_create(user=user)

        response_data = {
            "message": "Login successful",
            "token": token.key,
            "account": ParentMobileAccountSerializer(mobile_account).data
        }
        return Response(response_data, status=status.HTTP_200_OK)


class ParentsByLRNView(APIView):
    """
    Get parents/guardians by student LRN (for mobile registration)
    Endpoint: /api/parents/by-lrn/<lrn>/
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, lrn):
        try:
            student = Student.objects.get(lrn=lrn)
            parents = ParentGuardian.objects.filter(student=student)
            serializer = ParentGuardianSerializer(parents, many=True)
            return Response({
                "student": StudentSerializer(student).data,
                "parents_guardians": serializer.data
            })
        except Student.DoesNotExist:
            return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)


#new
class ParentGuardianPublicListView(APIView):
    """
    Lightweight read-only list so clients (like the mobile app) can fetch guardians
    by username, student LRN, or role without requiring teacher authentication.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        username = request.query_params.get('username')
        lrn = request.query_params.get('lrn')
        student_name = request.query_params.get('student')
        role = request.query_params.get('role')
        limit = request.query_params.get('limit')

        queryset = ParentGuardian.objects.select_related('student', 'teacher').all()
        if username:
            queryset = queryset.filter(username=username)
        if lrn:
            queryset = queryset.filter(student__lrn=lrn)
        if student_name:
            queryset = queryset.filter(student__name__iexact=student_name)
        if role:
            queryset = queryset.filter(role__iexact=role)
        if limit:
            try:
                limit_value = max(1, min(int(limit), 500))
                queryset = queryset[:limit_value]
            except (TypeError, ValueError):
                logger.warning("Invalid limit param for ParentGuardianPublicListView: %s", limit)

        serializer = ParentGuardianSerializer(queryset, many=True)
        return Response(serializer.data)

# new
class ParentLoginView(APIView):
    """
    Simple login for Parent/Guardian records stored in ParentGuardian model.
    This endpoint accepts POST { username, password } and returns the parent record
    if the plaintext password matches the stored `password` field.
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response({"error": "Username and password are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            pg = ParentGuardian.objects.get(username=username)
        except ParentGuardian.DoesNotExist:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)

        # Passwords are stored in plaintext in this model (per project choice)
        if (pg.password or "") != password:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ParentGuardianSerializer(pg)
        return Response({"parent": serializer.data}, status=status.HTTP_200_OK)

# new
class ParentDetailView(APIView):
    """Retrieve or partially update a ParentGuardian by primary key.

    Endpoint: GET/PATCH /api/parents/parent/<pk>/
    """
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, pk):
        try:
            parent = ParentGuardian.objects.get(pk=pk)
        except ParentGuardian.DoesNotExist:
            return Response({'error': 'Parent not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ParentGuardianSerializer(parent, context={'request': request})
        return Response(serializer.data)

    def patch(self, request, pk):
        try:
            parent = ParentGuardian.objects.get(pk=pk)
        except ParentGuardian.DoesNotExist:
            return Response({'error': 'Parent not found'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data

        logger.debug('ParentDetailView.patch called; request.FILES keys: %s', list(getattr(request, 'FILES', {}).keys()))

        # Accept both JSON and multipart form-data. Update known fields only.
        updated = False
        # Handle password change explicitly: require current_password match
        if isinstance(data, dict) and 'password' in data:
            new_pw = data.get('password')
            current_pw = data.get('current_password')
            if not current_pw:
                return Response({'error': 'current_password is required to change password.'}, status=status.HTTP_400_BAD_REQUEST)
            # simple plain-text compare (project currently stores plain passwords)
            if (parent.password or '') != str(current_pw):
                return Response({'error': 'Current password is incorrect.'}, status=status.HTTP_401_UNAUTHORIZED)
            parent.password = str(new_pw)
            updated = True
        for field in ('name', 'username', 'contact_number', 'address', 'email'):
            if field in data:
                setattr(parent, field, data.get(field))
                updated = True

        # handle avatar upload from multipart/form-data
        if getattr(request, 'FILES', None) and 'avatar' in request.FILES:
            uploaded = request.FILES['avatar']
            logger.debug('Saving uploaded avatar file: %s (size=%s)', uploaded.name, getattr(uploaded, 'size', 'unknown'))
            print(f"[ParentDetailView] received avatar file: {uploaded.name}, size={getattr(uploaded, 'size', 'unknown')}")
            parent.avatar = uploaded
            updated = True

        if updated:
            parent.save()
            # debug after save
            try:
                avatar_name = parent.avatar.name
                avatar_path = getattr(parent.avatar, 'path', None)
            except Exception:
                avatar_name = None
                avatar_path = None
            logger.debug('Parent saved. avatar.name=%s avatar.path=%s', avatar_name, avatar_path)
            print(f"[ParentDetailView] parent.save() completed. avatar.name={avatar_name} avatar.path={avatar_path}")
        serializer = ParentGuardianSerializer(parent, context={'request': request})
        debug_info = {'updated': updated, 'avatar_name': avatar_name if updated else None, 'avatar_path': avatar_path if updated else None}
        # Return serializer data at top-level (keeps previous client expectations) and include debug info
        response_data = dict(serializer.data)
        response_data['debug'] = debug_info
        return Response(response_data)

# new
class ParentNotificationListCreateView(APIView):
    """
    Read/create notifications tied to ParentGuardian records.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        parent_id = request.query_params.get('parent')
        lrn = request.query_params.get('lrn')
        limit = request.query_params.get('limit')

        queryset = ParentNotification.objects.select_related('parent', 'student').order_by('-created_at')
        if parent_id:
            queryset = queryset.filter(parent_id=parent_id)
        if lrn:
            queryset = queryset.filter(student__lrn=lrn)
        if limit:
            try:
                limit_value = max(1, min(int(limit), 200))
                queryset = queryset[:limit_value]
            except (TypeError, ValueError):
                logger.warning("Invalid limit param for notifications: %s", limit)

        serializer = ParentNotificationSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ParentNotificationSerializer(data=request.data)
        if serializer.is_valid():
            notification = serializer.save()
            output = ParentNotificationSerializer(notification).data
            return Response(output, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# new
class ParentEventListCreateView(APIView):
    """
    Read/create events tied to ParentGuardian records.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        parent_id = request.query_params.get('parent')
        lrn = request.query_params.get('lrn')
        limit = request.query_params.get('limit')
        upcoming = request.query_params.get('upcoming')

        logger.debug(
            "ParentEventListCreateView.get called parent=%s lrn=%s limit=%s upcoming=%s",
            parent_id,
            lrn,
            limit,
            upcoming,
        )

        queryset = ParentEvent.objects.select_related('parent', 'student').order_by('-scheduled_at', '-created_at')
        if parent_id:
            queryset = queryset.filter(parent_id=parent_id)
        if lrn:
            queryset = queryset.filter(student__lrn=lrn)
        if upcoming and str(upcoming).lower() in ('1', 'true', 'yes'):
            now = timezone.now()
            queryset = queryset.filter(
                Q(scheduled_at__gte=now) | Q(scheduled_at__isnull=True)
            )
        if limit:
            try:
                limit_value = max(1, min(int(limit), 200))
                queryset = queryset[:limit_value]
            except (TypeError, ValueError):
                logger.warning("Invalid limit param for events: %s", limit)

        serializer = ParentEventSerializer(queryset, many=True)
        logger.debug(
            "ParentEventListCreateView returning %s events",
            len(serializer.data)
        )
        return Response(serializer.data)

    def post(self, request):
        serializer = ParentEventSerializer(data=request.data)
        if serializer.is_valid():
            event = serializer.save()
            output = ParentEventSerializer(event).data
            return Response(output, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ParentScheduleListCreateView(APIView):
    """
    Read/create student schedule entries.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        parent_id = request.query_params.get('parent')
        student_id = request.query_params.get('student')
        lrn = request.query_params.get('lrn')
        teacher_id = request.query_params.get('teacher')
        day = request.query_params.get('day')
        upcoming = request.query_params.get('upcoming')
        limit = request.query_params.get('limit')

        queryset = ParentSchedule.objects.select_related('parent', 'student', 'teacher').order_by(
            'day_of_week', 'start_time', 'subject', 'created_at'
        )

        if parent_id:
            queryset = queryset.filter(parent_id=parent_id)
        if student_id:
            queryset = queryset.filter(student__pk=student_id)
        if lrn:
            queryset = queryset.filter(student__lrn=lrn)
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)
        if day:
            queryset = queryset.filter(day_of_week__iexact=str(day).lower())
        if upcoming and str(upcoming).lower() in ('1', 'true', 'yes'):
            now = timezone.localtime()
            today_day = now.strftime('%A').lower()
            current_time = now.time()
            queryset = queryset.filter(
                Q(day_of_week__iexact=today_day, start_time__gte=current_time)
                | Q(day_of_week__iexact=today_day, start_time__isnull=True)
                | Q(day_of_week__isnull=True)
                | Q(day_of_week='')
            )
        if limit:
            try:
                limit_value = max(1, min(int(limit), 500))
                queryset = queryset[:limit_value]
            except (TypeError, ValueError):
                logger.warning("Invalid limit param for schedules: %s", limit)

        serializer = ParentScheduleSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ParentScheduleSerializer(data=request.data)
        if serializer.is_valid():
            schedule = serializer.save()
            output = ParentScheduleSerializer(schedule).data
            return Response(output, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


