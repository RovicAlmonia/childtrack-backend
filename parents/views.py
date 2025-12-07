import logging
import json
from django.db import transaction
from django.db.models import Prefetch, Q
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import check_password, make_password
from django.conf import settings
import os
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.authtoken.models import Token

from django.utils import timezone
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
import base64
from django.core.files.base import ContentFile
from django.contrib.auth.forms import PasswordResetForm

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
    ParentNotificationSerializer,
    ParentEventSerializer,
    ParentScheduleSerializer,
)

logger = logging.getLogger(__name__)

import traceback


class AvatarDebugView(APIView):
    """Debug endpoint: check whether a media file exists on disk and return its URL.

    Query params:
      - file: relative path under MEDIA_ROOT (e.g. parent_avatars/jaymoelojo.png)
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        file_param = request.query_params.get('file')
        if not file_param:
            return Response({"error": "file query param required, e.g. ?file=parent_avatars/name.png"}, status=status.HTTP_400_BAD_REQUEST)

        # Normalize path to avoid path traversal
        file_rel = os.path.normpath(file_param).lstrip(os.sep)
        full_path = os.path.join(settings.MEDIA_ROOT, file_rel)
        exists = os.path.exists(full_path)

        # Build public URL (use settings.MEDIA_URL)
        media_url = getattr(settings, 'MEDIA_URL', '/media/')
        # Ensure leading slash on media_url
        if not media_url.startswith('/') and not media_url.startswith('http'):
            media_url = '/' + media_url

        # If MEDIA_URL is absolute already, use it; otherwise build absolute using request
        if media_url.startswith('http'):
            public_url = f"{media_url.rstrip('/')}/{file_rel}" if file_rel else None
        else:
            try:
                public_url = request.build_absolute_uri(f"{media_url.rstrip('/')}/{file_rel}")
            except Exception:
                public_url = f"{media_url.rstrip('/')}/{file_rel}"

        return Response({
            'file': file_rel,
            'exists_on_disk': exists,
            'full_path': full_path if exists else None,
            'public_url': public_url,
        })


class PasswordResetRequestView(APIView):
    """Public endpoint to request a password reset email.

    Expects POST { "email": "user@gmail.com" } and will send the
    Django password-reset email if the account exists. Permission: AllowAny
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email') if isinstance(request.data, dict) else None
        if not email:
            return Response({"error": "email is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            form = PasswordResetForm(data={"email": email})
            if form.is_valid():
                # use request to build absolute URLs in the email
                form.save(request=request, use_https=request.is_secure(), from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None))
                return Response({"message": "If that account exists we have sent a reset link to the provided email."}, status=status.HTTP_200_OK)
            else:
                # Don't leak whether the email exists; still return success-like message
                return Response({"message": "If that account exists we have sent a reset link to the provided email."}, status=status.HTTP_200_OK)
        except Exception as exc:
            logger.exception("Password reset request failed")
            return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
                "parents_guardians": ParentGuardianSerializer(created_records, many=True, context={'request': request}).data,
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
                "parents_guardians": ParentGuardianSerializer(created_records, many=True, context={'request': request}).data,
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
        try:
            teacher = TeacherProfile.objects.get(user=request.user)
            qs = ParentGuardian.objects.filter(teacher=teacher)
            
            # Optional LRN filter
            lrn = request.query_params.get('lrn')
            if lrn:
                qs = qs.filter(student__lrn=lrn)
            
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(qs, request)
            serializer = ParentGuardianSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        except TeacherProfile.DoesNotExist:
            return Response({"error": "Teacher profile not found"}, status=status.HTTP_404_NOT_FOUND)


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
            "parents_guardians": ParentGuardianSerializer(parents, many=True, context={'request': request}).data,
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
            serializer = ParentGuardianSerializer(parents, many=True, context={'request': request})
            return Response({
                "student": StudentSerializer(student).data,
                "parents_guardians": serializer.data
            })
        except Student.DoesNotExist:
            return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)


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

        serializer = ParentGuardianSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)


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


        # Support both hashed and legacy-plaintext passwords.
        valid = False
        try:
            if pg.password and check_password(password, pg.password):
                valid = True
            elif (pg.password or "") == password:
                # Legacy plaintext match: upgrade to hashed password on successful login
                pg.password = make_password(password)
                pg.save(update_fields=['password'])
                valid = True
        except Exception:
            # In case check_password/identify fails, fall back to plaintext compare
            if (pg.password or "") == password:
                pg.password = make_password(password)
                pg.save(update_fields=['password'])
                valid = True

        if not valid:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)

        # Try to serialize with request context so avatar_url is absolute.
        # If serialization fails for any reason, fall back to serializing
        # without the request context to avoid returning HTTP 500 to clients.
        try:
            serializer = ParentGuardianSerializer(pg, context={'request': request})
            parent_data = serializer.data
        except Exception as exc:
            logger.exception('ParentLoginView: serializer with request context failed')
            try:
                serializer = ParentGuardianSerializer(pg)
                parent_data = serializer.data
            except Exception:
                # Last-resort: return minimal info to avoid exposing internals
                logger.exception('ParentLoginView: fallback serializer also failed')
                return Response({"error": "Server error while preparing response"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"parent": parent_data}, status=status.HTTP_200_OK)


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
        # capture originals to decide if must_change_credentials can be cleared
        orig_username = parent.username
        orig_password = parent.password
        orig_must = getattr(parent, 'must_change_credentials', False)

        # Track what was changed
        changed_password = False
        changed_username = False

        # Handle password change explicitly: require current_password match
        if 'password' in data:
            new_pw = data.get('password')
            current_pw = data.get('current_password')

            # If this parent record is flagged as requiring credential change on first login,
            # allow changing the password without providing the current_password. This supports
            # the mobile first-login flow where temporary credentials were auto-generated.
            if orig_must:
                parent.password = make_password(str(new_pw))
                updated = True
                changed_password = True
                logger.info(f"Password changed for parent {parent.id} during forced credential update")
            else:
                # For voluntary changes, require current password
                if not current_pw:
                    return Response({'error': 'current_password is required to change password.'}, status=status.HTTP_400_BAD_REQUEST)

                # Support both hashed and legacy-plaintext stored passwords
                try:
                    if parent.password and check_password(str(current_pw), parent.password):
                        parent.password = make_password(str(new_pw))
                        updated = True
                        changed_password = True
                        logger.info(f"Password changed for parent {parent.id} via voluntary update (hashed match)")
                    elif (parent.password or '') == str(current_pw):
                        # Legacy plaintext match: accept and upgrade stored password
                        parent.password = make_password(str(new_pw))
                        updated = True
                        changed_password = True
                        logger.info(f"Password changed for parent {parent.id} via voluntary update (plaintext match)")
                    else:
                        return Response({'error': 'Current password is incorrect.'}, status=status.HTTP_401_UNAUTHORIZED)
                except Exception:
                    # Fallback to plaintext compare if hashing utilities fail
                    if (parent.password or '') == str(current_pw):
                        parent.password = make_password(str(new_pw))
                        updated = True
                        changed_password = True
                        logger.info(f"Password changed for parent {parent.id} via voluntary update (fallback)")
                    else:
                        return Response({'error': 'Current password is incorrect.'}, status=status.HTTP_401_UNAUTHORIZED)

        # Handle other fields
        for field in ('name', 'username', 'contact_number', 'address', 'email'):
            if field in data:
                # track username change
                if field == 'username':
                    new_un = data.get('username')
                    if new_un is not None and str(new_un) != (orig_username or ''):
                        changed_username = True
                        logger.info(f"Username changed for parent {parent.id}: '{orig_username}' -> '{new_un}'")
                setattr(parent, field, data.get(field))
                updated = True

        # Support base64 avatar uploads using 'avatar_base64' (or 'photo_base64')
        avatar_base64 = data.get('avatar_base64') or data.get('photo_base64')
        if avatar_base64:
            try:
                if 'base64,' in avatar_base64:
                    avatar_base64 = avatar_base64.split('base64,')[1]
                avatar_data = base64.b64decode(avatar_base64)
                avatar_name = f"parent_{(parent.name or 'parent').replace(' ', '_')}_{parent.id}.jpg"
                parent.avatar = ContentFile(avatar_data, name=avatar_name)
                updated = True
                logger.info('Parent %s avatar set from base64 payload', parent.id)
            except Exception as e:
                logger.exception('Error processing base64 avatar for parent %s: %s', pk, str(e))

        # handle multipart/form-data file upload (fallback)
        if getattr(request, 'FILES', None) and ('avatar' in request.FILES or 'photo' in request.FILES):
            uploaded = request.FILES.get('avatar') or request.FILES.get('photo')
            logger.debug('Saving uploaded avatar file: %s (size=%s)', uploaded.name, getattr(uploaded, 'size', 'unknown'))
            print(f"[ParentDetailView] received avatar file: {uploaded.name}, size={getattr(uploaded, 'size', 'unknown')}")
            parent.avatar = uploaded
            updated = True

        if updated:
            # CRITICAL FIX: Clear must_change_credentials flag when credentials are properly updated
            if orig_must:
                # During forced update, require password to be changed (username is optional but recommended)
                if changed_password:
                    parent.must_change_credentials = False
                    logger.info(f"Clearing must_change_credentials for parent {parent.id} - password changed (username also changed: {changed_username})")
                else:
                    logger.warning(f"Parent {parent.id} must_change_credentials NOT cleared - password not changed (username changed: {changed_username})")
            
            parent.save()
            
            # debug after save
            try:
                avatar_name = parent.avatar.name
                avatar_path = getattr(parent.avatar, 'path', None)
            except Exception:
                avatar_name = None
                avatar_path = None
            logger.debug('Parent saved. avatar.name=%s avatar.path=%s', avatar_name, avatar_path)
            logger.info(f"Parent {parent.id} saved - must_change_credentials: {parent.must_change_credentials}")
            print(f"[ParentDetailView] parent.save() completed. avatar.name={avatar_name} avatar.path={avatar_path}")
        else:
            avatar_name = None
            avatar_path = None
            
        serializer = ParentGuardianSerializer(parent, context={'request': request})
        debug_info = {
            'updated': updated,
            'avatar_name': avatar_name,
            'avatar_path': avatar_path,
            'must_change_credentials': parent.must_change_credentials,
            'changed_username': changed_username,
            'changed_password': changed_password,
        }
        
        # Return serializer data at top-level (keeps previous client expectations) and include debug info
        response_data = dict(serializer.data)
        response_data['debug'] = debug_info
        return Response(response_data)

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


class ParentEventListCreateView(APIView):
    """
    Announcements API for teachers to create and parents/mobile app to fetch.
    
    Teachers POST: Create announcements visible to all their students' parents
    Parents/Mobile GET: Fetch announcements from their student's teacher
    Endpoint: /api/parents/events/
    """
    
    def get_permissions(self):
        """GET requests: allow unauthenticated (for mobile app flexibility)
           POST requests: require authenticated teacher only"""
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get(self, request):
        """
        Fetch announcements/events
        Query params:
        - teacher_id: Filter by specific teacher
        - lrn: Filter by student LRN (parents only)
        - parent_id: Filter by parent (parents only)
        - upcoming: Show only future events (1/true/yes)
        - limit: Max number of results (default 200)
        """
        queryset = ParentEvent.objects.select_related(
            'teacher', 'parent', 'student'
        ).order_by('-scheduled_at', '-created_at')

        # Debug: log incoming query params for troubleshooting mobile clients
        try:
            logger.info('ParentEventListCreateView GET called with params: %s', dict(request.query_params))
        except Exception:
            logger.info('ParentEventListCreateView GET called')

        # If authenticated user is a parent, automatically filter to their teacher
        user = request.user
        if user and user.is_authenticated:
            try:
                parent = ParentGuardian.objects.get(user=user)
                # Parent only sees announcements from their student's teacher
                queryset = queryset.filter(teacher=parent.teacher)
                logger.info(f"Parent {parent.id} viewing events from teacher {parent.teacher.id}")
            except ParentGuardian.DoesNotExist:
                # If not a parent, don't auto-filter (teachers can see all)
                logger.info(f"User {user.id} authenticated but not a parent - showing all events")
                pass

        # Optional filters
        teacher_id = request.query_params.get('teacher_id')
        parent_id = request.query_params.get('parent')
        lrn = request.query_params.get('lrn')
        section = request.query_params.get('section')
        upcoming = request.query_params.get('upcoming')
        limit = request.query_params.get('limit')

        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)
        # Filter by section: include events explicitly targeted to the section,
        # events attached to a student in that section, or broadcast events
        # (section is null) when appropriate.
        if section:
            queryset = queryset.filter(
                Q(section__isnull=True) | Q(section__iexact=section) | Q(student__section__iexact=section)
            )
        
        if parent_id:
            queryset = queryset.filter(Q(parent_id=parent_id) | Q(parent__isnull=True))
        
        if lrn:
            queryset = queryset.filter(Q(student__lrn=lrn) | Q(student__isnull=True))
        
        if upcoming and str(upcoming).lower() in ('1', 'true', 'yes'):
            now = timezone.now()
            queryset = queryset.filter(scheduled_at__gte=now)
        
        if limit:
            try:
                limit_value = max(1, min(int(limit), 500))
                queryset = queryset[:limit_value]
            except (TypeError, ValueError):
                logger.warning("Invalid limit param for events: %s", limit)

        # Log how many events match before serialization (helps debug empty client views)
        try:
            matched_count = queryset.count()
            logger.info('ParentEventListCreateView matched events: %d', matched_count)
        except Exception:
            logger.debug('Could not determine matched_count for events')

        serializer = ParentEventSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        """
        Create announcement (teachers only)
        
        Required fields:
        - title: Announcement title
        - description: Announcement content
        - event_type: Type (e.g. 'Announcement', 'Alert', 'Reminder')
        - scheduled_at: ISO datetime when to publish
        
        Optional:
        - parent_id: Target specific parent (null = all parents)
        - student_id: Target specific student (null = all students)
        - location: Physical location (if applicable)
        """
        try:
            teacher = TeacherProfile.objects.get(user=request.user)
        except TeacherProfile.DoesNotExist:
            return Response(
                {"error": "Only teachers can create announcements"},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ParentEventSerializer(data=request.data)
        if serializer.is_valid():
            # Allow events to target a specific section by providing `section` in payload.
            section_value = request.data.get('section')
            event = serializer.save(
                teacher=teacher,
                parent=None,
                section=section_value,
            )

            logger.info(f"Teacher {teacher.id} created announcement: {event.title} (section={section_value})")

            # Create notifications for parents in the targeted section (if provided).
            try:
                if section_value:
                    # Find parents whose student is in the given section and whose teacher is this teacher
                    parents_qs = ParentGuardian.objects.filter(student__section__iexact=section_value, teacher=teacher)
                    notifications = []
                    for p in parents_qs:
                        try:
                            notif = ParentNotification(
                                parent=p,
                                student=p.student,
                                type='event',
                                message=f"{event.title}: {event.description or ''}",
                                extra_data=json.dumps({'event_id': event.id})
                            )
                            notifications.append(notif)
                        except Exception:
                            continue
                    if notifications:
                        ParentNotification.objects.bulk_create(notifications)

            except Exception:
                logger.exception('Failed to create section notifications')

            output = ParentEventSerializer(event).data
            return Response(output, status=status.HTTP_201_CREATED)
        
        logger.warning(f"Announcement creation failed with errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ParentEventDetailView(APIView):
    """
    Retrieve, update, or delete a specific event/announcement
    Endpoint: /api/parents/events/{id}/
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        """Get single announcement"""
        try:
            event = ParentEvent.objects.select_related('teacher', 'parent', 'student').get(pk=pk)
        except ParentEvent.DoesNotExist:
            return Response({"error": "Announcement not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ParentEventSerializer(event)
        return Response(serializer.data)

    def patch(self, request, pk):
        """Update announcement (teachers only)"""
        try:
            event = ParentEvent.objects.get(pk=pk)
        except ParentEvent.DoesNotExist:
            return Response({"error": "Announcement not found"}, status=status.HTTP_404_NOT_FOUND)

        # Only the teacher who created it can update
        try:
            teacher = TeacherProfile.objects.get(user=request.user)
            if event.teacher != teacher:
                return Response(
                    {"error": "You can only update your own announcements"},
                    status=status.HTTP_403_FORBIDDEN
                )
        except TeacherProfile.DoesNotExist:
            return Response(
                {"error": "Only teachers can update announcements"},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ParentEventSerializer(event, data=request.data, partial=True)
        if serializer.is_valid():
            updated_event = serializer.save()
            logger.info(f"Teacher {teacher.id} updated announcement: {updated_event.title}")
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Delete announcement (teachers only)"""
        try:
            event = ParentEvent.objects.get(pk=pk)
        except ParentEvent.DoesNotExist:
            return Response({"error": "Announcement not found"}, status=status.HTTP_404_NOT_FOUND)

        # Only the teacher who created it can delete
        try:
            teacher = TeacherProfile.objects.get(user=request.user)
            if event.teacher != teacher:
                return Response(
                    {"error": "You can only delete your own announcements"},
                    status=status.HTTP_403_FORBIDDEN
                )
        except TeacherProfile.DoesNotExist:
            return Response(
                {"error": "Only teachers can delete announcements"},
                status=status.HTTP_403_FORBIDDEN
            )

        logger.info(f"Teacher {teacher.id} deleted announcement: {event.title}")
        event.delete()
        return Response({"message": "Announcement deleted successfully"}, status=status.HTTP_204_NO_CONTENT)


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

