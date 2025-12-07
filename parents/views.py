import logging
import json
from django.db import transaction
from django.db.models import Prefetch, Q
from django.contrib.auth import authenticate
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
from django.contrib.auth.hashers import check_password, make_password, identify_hasher

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

from django.shortcuts import redirect
from django.core.files.storage import default_storage
from django.http import FileResponse
import mimetypes

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


class AvatarRedirectView(APIView):
    """Redirect to a parent's avatar URL (absolute or built from MEDIA_URL).

    This allows admin links or other UIs to point to a stable endpoint like
    `/api/parents/avatar/<pk>/` which will redirect to the actual image URL.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        try:
            parent = ParentGuardian.objects.get(pk=pk)
        except ParentGuardian.DoesNotExist:
            return Response({'error': 'Parent not found'}, status=status.HTTP_404_NOT_FOUND)

        if not getattr(parent, 'avatar', None):
            return Response({'error': 'No avatar for this parent'}, status=status.HTTP_404_NOT_FOUND)

        try:
            avatar_url = parent.avatar.url
        except Exception:
            avatar_url = None

        # If avatar_url is absolute, redirect directly
        if avatar_url and isinstance(avatar_url, str) and avatar_url.startswith('http'):
            return redirect(avatar_url)

        # If avatar is stored locally (relative path), try to serve it directly
        try:
            file_name = parent.avatar.name if getattr(parent.avatar, 'name', None) else None
            if file_name and default_storage.exists(file_name):
                # Serve the file content via FileResponse so admin clicks work even
                # when MEDIA URLs are not publicly routed by the web server.
                fh = default_storage.open(file_name, 'rb')
                content_type = mimetypes.guess_type(file_name)[0] or 'application/octet-stream'
                return FileResponse(fh, content_type=content_type)
        except Exception:
            # Fall through to other resolution strategies
            pass

        # Try to build absolute URI using request if avatar_url is a relative path
        try:
            if avatar_url:
                return redirect(request.build_absolute_uri(avatar_url))
        except Exception:
            pass

        # Final fallback: attempt to construct from MEDIA_URL + file name
        try:
            media_url = getattr(settings, 'MEDIA_URL', '/media/')
            file_name = parent.avatar.name if getattr(parent.avatar, 'name', None) else None
            if file_name:
                if media_url.startswith('http'):
                    return redirect(f"{media_url.rstrip('/')}/{file_name}")
                return redirect(request.build_absolute_uri(f"{media_url.rstrip('/')}/{file_name}"))
        except Exception:
            pass

        return Response({'error': 'Unable to determine or serve avatar URL'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AvatarDebugInfoView(APIView):
    """Return diagnostic info about a parent's avatar for deployed troubleshooting.

    Fields returned:
      - avatar_url: the value of `parent.avatar.url` (may be absolute or relative)
      - avatar_name: the storage name/path of the file
      - storage_exists: whether `default_storage.exists(avatar_name)` returns True
      - default_file_storage: Django's `DEFAULT_FILE_STORAGE` setting
      - media_url: settings.MEDIA_URL
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        try:
            parent = ParentGuardian.objects.get(pk=pk)
        except ParentGuardian.DoesNotExist:
            return Response({'error': 'Parent not found'}, status=status.HTTP_404_NOT_FOUND)

        avatar_url = None
        avatar_name = None
        storage_exists = None
        try:
            avatar_url = parent.avatar.url if getattr(parent, 'avatar', None) else None
        except Exception:
            avatar_url = None

        try:
            avatar_name = parent.avatar.name if getattr(parent, 'avatar', None) else None
        except Exception:
            avatar_name = None

        try:
            storage_exists = default_storage.exists(avatar_name) if avatar_name else False
        except Exception:
            storage_exists = None

        data = {
            'avatar_url': avatar_url,
            'avatar_name': avatar_name,
            'storage_exists': storage_exists,
            'default_file_storage': getattr(settings, 'DEFAULT_FILE_STORAGE', None),
            'media_url': getattr(settings, 'MEDIA_URL', None),
        }
        return Response(data)


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
            serializer = ParentGuardianSerializer(parents, many=True)
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

        try:
            pg = ParentGuardian.objects.get(username=username)
        except ParentGuardian.DoesNotExist:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)

        stored = pg.password or ''
        # Determine if stored password is hashed
        try:
            identify_hasher(stored)
            stored_hashed = True
        except Exception:
            stored_hashed = False

        valid = False
        if stored_hashed:
            valid = check_password(password, stored)
        else:
            # fallback for legacy plain-text passwords: allow login and migrate to hashed
            if stored == password:
                valid = True
                try:
                    pg.password = make_password(password)
                    pg.save(update_fields=['password'])
                except Exception:
                    # best-effort migration; continue even if migration fails
                    pass

        if not valid:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ParentGuardianSerializer(pg)
        return Response({"parent": serializer.data}, status=status.HTTP_200_OK)


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

        # Capture originals to decide if must_change_credentials can be cleared
        orig_username = parent.username
        orig_password = parent.password
        orig_must = getattr(parent, 'must_change_credentials', False)

        # Track what was changed
        updated = False
        changed_password = False
        changed_username = False

        # Handle password change explicitly: require current_password match
        if 'password' in data:
            new_pw = data.get('password')
            current_pw = data.get('current_password')

            if orig_must:
                # For forced changes, accept any password without current_password verification
                parent.password = make_password(str(new_pw))
                updated = True
                changed_password = True
                logger.info(f"Password changed for parent {parent.id} during forced credential update")
            else:
                # For voluntary changes, require current password
                if not current_pw:
                    return Response({'error': 'current_password is required to change password.'}, status=status.HTTP_400_BAD_REQUEST)

                stored = parent.password or ''
                try:
                    identify_hasher(stored)
                    stored_hashed = True
                except Exception:
                    stored_hashed = False

                # Verify current password
                if stored_hashed:
                    if not check_password(current_pw, stored):
                        return Response({'error': 'Current password is incorrect.'}, status=status.HTTP_401_UNAUTHORIZED)
                else:
                    if stored != str(current_pw):
                        return Response({'error': 'Current password is incorrect.'}, status=status.HTTP_401_UNAUTHORIZED)
                    else:
                        # Migrate legacy plain-text to hashed
                        try:
                            parent.password = make_password(str(current_pw))
                        except Exception:
                            pass

                parent.password = make_password(str(new_pw))
                updated = True
                changed_password = True
                logger.info(f"Password changed for parent {parent.id} via voluntary update")

        # FIXED: Handle ALL text fields including username
        for field in ('name', 'username', 'contact_number', 'address', 'email'):
            if field in data:
                value = data.get(field)
                
                # Track username changes
                if field == 'username':
                    if value is not None and str(value) != (orig_username or ''):
                        changed_username = True
                        logger.info(f"Username changed for parent {parent.id}: '{orig_username}' -> '{value}'")
                
                setattr(parent, field, value)
                updated = True

        # CRITICAL: Handle avatar upload from multipart/form-data
        if request.FILES and ('avatar' in request.FILES or 'photo' in request.FILES):
            uploaded = request.FILES.get('avatar') or request.FILES.get('photo')
            logger.info(f'Received avatar file upload: {uploaded.name}, size={uploaded.size}')
            print(f"[ParentDetailView] received avatar file: {uploaded.name}, size={uploaded.size}")
            parent.avatar = uploaded
            updated = True
        
        # Support base64 avatar uploads (fallback for some mobile clients)
        avatar_base64 = data.get('avatar_base64') or data.get('photo_base64')
        if avatar_base64 and not request.FILES:
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

        if updated:
            # Clear must_change_credentials flag when credentials are properly updated
            if orig_must and changed_password:
                parent.must_change_credentials = False
                logger.info(f"Clearing must_change_credentials for parent {parent.id} - password changed (username also changed: {changed_username})")
            
            # Save the parent record
            try:
                parent.save()
                logger.info(f"Parent {parent.id} saved successfully")
                
                # Log avatar details after save
                if parent.avatar:
                    logger.info(f"Avatar saved: name={parent.avatar.name}, url={parent.avatar.url}")
                    print(f"[ParentDetailView] Avatar saved: name={parent.avatar.name}, url={parent.avatar.url}")
            except Exception as e:
                logger.exception(f"Error saving parent {parent.id}: {e}")
                print(f"[ParentDetailView] ERROR saving parent: {e}")
                return Response({'error': f'Failed to save: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Serialize and return response
        serializer = ParentGuardianSerializer(parent, context={'request': request})
        response_data = serializer.data
        
        # Add debug info
        response_data['debug'] = {
            'updated': updated,
            'avatar_saved': bool(parent.avatar),
            'avatar_url': parent.avatar.url if parent.avatar else None,
            'avatar_name': parent.avatar.name if parent.avatar else None,
            'must_change_credentials': parent.must_change_credentials,
            'changed_username': changed_username,
            'changed_password': changed_password,
        }
        
        logger.info(f"ParentDetailView PATCH complete for parent {parent.id}: {response_data['debug']}")
        
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

