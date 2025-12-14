from django.contrib.auth import authenticate
from django.db import IntegrityError
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from .models import TeacherProfile, Attendance, Absence, Dropout, UnauthorizedPerson
from .serializers import (
    TeacherProfileSerializer,
    AttendanceSerializer,
    AbsenceSerializer,
    DropoutSerializer,
    UnauthorizedPersonSerializer
)
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Alignment, Font
from openpyxl.drawing.fill import GradientFillProperties, GradientStop
from datetime import datetime
from collections import defaultdict
from calendar import monthrange
from zoneinfo import ZoneInfo
import io
import json
import re

# ========================================
# TEACHER REGISTRATION (Public)
# ========================================
class RegisterView(generics.CreateAPIView):
    """Register a new teacher account"""
    queryset = TeacherProfile.objects.all()
    serializer_class = TeacherProfileSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            teacher_profile = serializer.save()
            token, _ = Token.objects.get_or_create(user=teacher_profile.user)
            return Response({
                "message": "Registration successful!",
                "token": token.key,
                "teacher": {
                    "id": teacher_profile.id,
                    "name": teacher_profile.user.first_name or teacher_profile.user.username,
                    "username": teacher_profile.user.username,
                    "section": teacher_profile.section,
                }
            }, status=status.HTTP_201_CREATED)
        except IntegrityError:
            return Response(
                {"error": "Username already exists."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"Registration failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# ========================================
# TEACHER LOGIN (Public)
# ========================================
class LoginView(APIView):
    """Authenticate teacher and return token"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        username = request.data.get("username") or request.data.get("name")
        password = request.data.get("password")
        grade = request.data.get("grade")

        if not username or not password:
            return Response(
                {"error": "Username and password are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(username=username, password=password)
        if user:
            try:
                teacher_profile = TeacherProfile.objects.get(user=user)
                if grade and grade.lower() not in teacher_profile.section.lower():
                    return Response(
                        {"error": "Grade does not match your assigned section"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                token, _ = Token.objects.get_or_create(user=user)
                return Response({
                    "token": token.key,
                    "teacher": {
                        "id": teacher_profile.id,
                        "name": user.first_name or username,
                        "username": username,
                        "section": teacher_profile.section,
                    }
                }, status=status.HTTP_200_OK)
            except TeacherProfile.DoesNotExist:
                return Response(
                    {"error": "Teacher profile not found"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return Response(
            {"error": "Invalid credentials"},
            status=status.HTTP_400_BAD_REQUEST
        )

# ========================================
# ATTENDANCE VIEWS
# ========================================
class AttendanceView(APIView):
    """List and create attendance records"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get all attendance records with optional filters"""
        try:
            teacher_profile = TeacherProfile.objects.filter(user=request.user).first()
            if not teacher_profile:
                return Response(
                    {"error": "Teacher profile not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Apply filters
            date = request.query_params.get('date')
            student = request.query_params.get('student')
            status_filter = request.query_params.get('status')
            transaction_type = request.query_params.get('transaction_type')

            queryset = Attendance.objects.filter(teacher=teacher_profile)

            if date:
                queryset = queryset.filter(date=date)
            if student:
                queryset = queryset.filter(student_name__icontains=student)
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            if transaction_type:
                queryset = queryset.filter(transaction_type=transaction_type)

            attendances = queryset.order_by('-date', '-timestamp')
            serializer = AttendanceSerializer(attendances, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response(
                {"error": f"Error fetching attendance: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        """Create a new attendance record"""
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            data = request.data.copy()
            qr_data = data.get('qr_data', '')

            # Parse QR code data if provided
            if qr_data:
                try:
                    qr_json = json.loads(qr_data)
                    data['student_lrn'] = qr_json.get('lrn', '')
                    if not data.get('student_name'):
                        data['student_name'] = qr_json.get('student', 'Unknown')

                    # ✅ EXTRACT GENDER FROM QR CODE
                    qr_gender = qr_json.get('gender', '').strip().upper()
                    if qr_gender:
                        # Convert F/M to Female/Male
                        if qr_gender == 'F' or qr_gender == 'FEMALE':
                            data['gender'] = 'Female'
                        elif qr_gender == 'M' or qr_gender == 'MALE':
                            data['gender'] = 'Male'

                    # ✅ EXTRACT GUARDIAN NAME FROM QR CODE
                    guardian_name = qr_json.get('name', '').strip()
                    guardian_role = qr_json.get('role', '').strip()
                    if guardian_name:
                        data['guardian_name'] = guardian_name

                except json.JSONDecodeError:
                    pass

            # Set default date if not provided
            if not data.get('date'):
                data['date'] = datetime.now().date()

            # Determine session based on Philippine Time if not provided
            if not data.get('session'):
                now = datetime.now()
                ph_time = now.astimezone(ZoneInfo('Asia/Manila'))
                data['session'] = 'AM' if ph_time.hour < 12 else 'PM'

            # ✅ NEW: Determine transaction type based on status
            status_value = data.get('status', 'Present')
            if status_value == 'Drop-off':
                data['transaction_type'] = 'drop-off'
            elif status_value == 'Pick-up':
                data['transaction_type'] = 'pick-up'
            else:
                data['transaction_type'] = 'attendance'

            serializer = AttendanceSerializer(data=data)
            if serializer.is_valid():
                serializer.save(teacher=teacher_profile)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except TeacherProfile.DoesNotExist:
            return Response(
                {"error": "Teacher profile not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def attendance_detail(request, pk):
    """Retrieve, update, or delete a specific attendance record"""
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
        attendance = get_object_or_404(Attendance, pk=pk)

        if request.method == 'GET':
            serializer = AttendanceSerializer(attendance)
            return Response(serializer.data)

        elif request.method in ['PUT', 'PATCH']:
            partial = request.method == 'PATCH'
            
            # ✅ NEW: Update transaction_type if status is being changed
            data = request.data.copy()
            if 'status' in data:
                status_value = data['status']
                if status_value == 'Drop-off':
                    data['transaction_type'] = 'drop-off'
                elif status_value == 'Pick-up':
                    data['transaction_type'] = 'pick-up'
                else:
                    data['transaction_type'] = 'attendance'
            
            serializer = AttendanceSerializer(
                attendance,
                data=data,
                partial=partial
            )
            if serializer.is_valid():
                serializer.save(teacher=teacher_profile)
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        elif request.method == 'DELETE':
            attendance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    except TeacherProfile.DoesNotExist:
        return Response(
            {"error": "Teacher profile not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Attendance.DoesNotExist:
        return Response(
            {"error": "Attendance record not found"},
            status=status.HTTP_404_NOT_FOUND
        )

# ========================================
# PUBLIC ATTENDANCE LIST
# ========================================
class PublicAttendanceListView(generics.ListAPIView):
    """Public endpoint to view all attendance records (no authentication required)"""
    queryset = Attendance.objects.all().order_by('-timestamp')
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

# ========================================
# ABSENCE VIEWS
# ========================================
class AbsenceView(APIView):
    """List and create absence records"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get all absence records for the authenticated teacher"""
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            absences = Absence.objects.filter(teacher=teacher_profile).order_by('-date')
            serializer = AbsenceSerializer(absences, many=True)
            return Response(serializer.data)
        except TeacherProfile.DoesNotExist:
            return Response(
                {"error": "Teacher profile not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    def post(self, request):
        """Create a new absence record"""
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            serializer = AbsenceSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(teacher=teacher_profile)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except TeacherProfile.DoesNotExist:
            return Response(
                {"error": "Teacher profile not found"},
                status=status.HTTP_404_NOT_FOUND
            )

@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def absence_detail(request, pk):
    """Retrieve, update, or delete a specific absence record"""
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
        absence = get_object_or_404(Absence, pk=pk, teacher=teacher_profile)

        if request.method == 'GET':
            serializer = AbsenceSerializer(absence)
            return Response(serializer.data)

        elif request.method in ['PUT', 'PATCH']:
            partial = request.method == 'PATCH'
            serializer = AbsenceSerializer(
                absence,
                data=request.data,
                partial=partial
            )
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        elif request.method == 'DELETE':
            absence.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    except TeacherProfile.DoesNotExist:
        return Response(
            {"error": "Teacher profile not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Absence.DoesNotExist:
        return Response(
            {"error": "Absence not found"},
            status=status.HTTP_404_NOT_FOUND
        )

# ========================================
# DROPOUT VIEWS
# ========================================
class DropoutView(APIView):
    """List and create dropout records"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get all dropout records for the authenticated teacher"""
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            dropouts = Dropout.objects.filter(teacher=teacher_profile).order_by('-date')
            serializer = DropoutSerializer(dropouts, many=True)
            return Response(serializer.data)
        except TeacherProfile.DoesNotExist:
            return Response(
                {"error": "Teacher profile not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    def post(self, request):
        """Create a new dropout record"""
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            serializer = DropoutSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(teacher=teacher_profile)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except TeacherProfile.DoesNotExist:
            return Response(
                {"error": "Teacher profile not found"},
                status=status.HTTP_404_NOT_FOUND
            )

@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def dropout_detail(request, pk):
    """Retrieve, update, or delete a specific dropout record"""
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
        dropout = get_object_or_404(Dropout, pk=pk, teacher=teacher_profile)

        if request.method == 'GET':
            serializer = DropoutSerializer(dropout)
            return Response(serializer.data)

        elif request.method in ['PUT', 'PATCH']:
            partial = request.method == 'PATCH'
            serializer = DropoutSerializer(
                dropout,
                data=request.data,
                partial=partial
            )
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        elif request.method == 'DELETE':
            dropout.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    except TeacherProfile.DoesNotExist:
        return Response(
            {"error": "Teacher profile not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Dropout.DoesNotExist:
        return Response(
            {"error": "Dropout not found"},
            status=status.HTTP_404_NOT_FOUND
        )

# ========================================
# UNAUTHORIZED PERSON VIEWS
# ========================================
class UnauthorizedPersonView(APIView):
    """List and create unauthorized person records"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get all unauthorized person records for the authenticated teacher"""
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            persons = UnauthorizedPerson.objects.filter(
                teacher=teacher_profile
            ).order_by('-timestamp')
            serializer = UnauthorizedPersonSerializer(persons, many=True)
            return Response(serializer.data)
        except TeacherProfile.DoesNotExist:
            return Response(
                {"error": "Teacher profile not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    def post(self, request):
        """Create a new unauthorized person record"""
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            serializer = UnauthorizedPersonSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(teacher=teacher_profile)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except TeacherProfile.DoesNotExist:
            return Response(
                {"error": "Teacher profile not found"},
                status=status.HTTP_404_NOT_FOUND
            )

@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def unauthorized_person_detail(request, pk):
    """Retrieve, update, or delete a specific unauthorized person record"""
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
        person = get_object_or_404(
            UnauthorizedPerson,
            pk=pk,
            teacher=teacher_profile
        )

        if request.method == 'GET':
            serializer = UnauthorizedPersonSerializer(person)
            return Response(serializer.data)

        elif request.method in ['PUT', 'PATCH']:
            partial = request.method == 'PATCH'
            serializer = UnauthorizedPersonSerializer(
                person,
                data=request.data,
                partial=partial
            )
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        elif request.method == 'DELETE':
            person.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    except TeacherProfile.DoesNotExist:
        return Response(
            {"error": "Teacher profile not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except UnauthorizedPerson.DoesNotExist:
        return Response(
            {"error": "Person not found"},
            status=status.HTTP_404_NOT_FOUND
        )

# ========================================
# SF2 EXCEL REPORT GENERATION
# ========================================
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_sf2_excel(request):
    """
    Generate SF2 Excel report with attendance data for a specific month.
    Separates students by gender: Boys start at row 14, Girls start at row 36.
    ONLY WEEKDAYS (Monday-Friday) are included in the calendar.
    
    NAME FORMAT:
    - Column B (Row 14+): FULL NAME (Last Name, First Name Middle Name)
    
    Visual Legend:
    - AM Present (Morning): Green triangle ◤ - Middle vertical, Justify horizontal (fills left side)
    - PM Present (Afternoon): Green triangle ◢ - Middle vertical, Left horizontal (on right side)
    - Full Day Present (AM + PM): Solid green fill
    - Absent: Solid red fill
    
    Request Parameters:
    - template_file: Excel template file (multipart/form-data)
    - month: Optional, integer 1-12 (defaults to current month)
    - year: Optional, integer (defaults to current year)
    """
    try:
        # Get authenticated teacher profile
        teacher_profile = TeacherProfile.objects.get(user=request.user)

        # Validate template file upload
        template_file = request.FILES.get('template_file')
        if not template_file:
            return Response(
                {"error": "Please upload an SF2 template file."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Load the Excel workbook
        try:
            wb = load_workbook(template_file)
        except Exception as e:
            return Response(
                {"error": f"Failed to load Excel template: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get and validate month/year parameters
        try:
            month = int(request.POST.get('month', datetime.now().month))
            year = int(request.POST.get('year', datetime.now().year))
        except ValueError:
            return Response(
                {"error": "Invalid month or year parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate month range
        if month < 1 or month > 12:
            return Response(
                {"error": "Month must be between 1 and 12"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Month names
        month_names = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                      "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

        # Day names - EXACT ORDER: Mon, Tue, Wed, Thu, Fri only (weekdays)
        day_names_short = ["Mon", "Tue", "Wed", "Thu", "Fri"]

        # Fetch attendance records for the SPECIFIC MONTH only
        attendances = Attendance.objects.filter(
            teacher=teacher_profile,
            date__year=year,
            date__month=month
        ).order_by('date', 'timestamp')

        print(f"📊 Fetching attendance for: {month_names[month-1]} {year}")
        print(f"📝 Found {attendances.count()} attendance records")

        # Build attendance data structure
        attendance_data = defaultdict(
            lambda: {'days': defaultdict(lambda: {'am': False, 'pm': False}), 'gender': None}
        )

        # Set to collect all unique students with gender
        students_dict = {}  # {name: gender}

        # Process each attendance record
        for att in attendances:
            student_name = att.student_name
            day = att.date.day

            # Store student gender if we don't have it yet
            if student_name not in students_dict:
                students_dict[student_name] = att.gender if hasattr(att, 'gender') and att.gender else 'Male'

            # Determine session with better fallback logic
            if hasattr(att, 'session') and att.session:
                session = att.session.upper()
            elif att.timestamp:
                # Use Philippine timezone for consistent session determination
                ph_time = att.timestamp.astimezone(ZoneInfo('Asia/Manila'))
                session = 'AM' if ph_time.hour < 12 else 'PM'
            else:
                session = 'AM'  # Default fallback

            # Mark attendance only if status is NOT 'Absent'
            if att.status and att.status.lower() != 'absent':
                if session == 'AM':
                    attendance_data[student_name]['days'][day]['am'] = True
                elif session == 'PM':
                    attendance_data[student_name]['days'][day]['pm'] = True

            # Store gender
            attendance_data[student_name]['gender'] = students_dict[student_name]

        # Separate students by gender and sort alphabetically
        boys = sorted([name for name, gender in students_dict.items() 
                      if gender and gender.lower() == 'male'])
        girls = sorted([name for name, gender in students_dict.items() 
                       if gender and gender.lower() == 'female'])

        print(f"👦 Boys: {len(boys)} students")
        print(f"👧 Girls: {len(girls)} students")

        # Current date information
        now = datetime.now()
        current_day = now.day
        current_year = now.year
        current_month = now.month

        # Define cell styling
        red_fill = PatternFill(start_color='FF0000', end_color='FF0000', fill_type='solid')
        green_fill = PatternFill(start_color='00B050', end_color='00B050', fill_type='solid')

        # Triangle font - LARGE size (48pt) with green color
        triangle_font = Font(color="00B050", size=48, bold=True)
        center_alignment = Alignment(horizontal='center', vertical='center')
        left_alignment = Alignment(horizontal='left', vertical='center')

        # CORRECT TRIANGLE ALIGNMENTS
        # AM (morning) = ◤ - Middle vertical + Justify horizontal (left-aligned effect)
        am_triangle_alignment = Alignment(
            horizontal='justify',  # Justify pushes content to fill space
            vertical='center',     # Middle vertical alignment
            wrap_text=False,
            shrink_to_fit=False
        )

        # PM (afternoon) = ◢ - Middle vertical + Left horizontal
        pm_triangle_alignment = Alignment(
            horizontal='left',     # Left horizontal alignment
            vertical='center',     # Middle vertical alignment
            wrap_text=False,
            shrink_to_fit=False
        )

        # Use the first sheet from the template
        if len(wb.sheetnames) > 0:
            sheet_name = wb.sheetnames[0]
            ws = wb[sheet_name]
            print(f"📄 Processing sheet: {sheet_name}")
        else:
            return Response(
                {"error": "No sheets found in template"},
                status=status.HTTP_400_BAD_REQUEST
            )

        month_name = month_names[month - 1]
        print(f"📅 Filling data for: {month_name} {year}")

        # Template Configuration
        date_row = 11           # Row 11: Dates (1-31)
        day_row = 12            # Row 12: Day names (Mon, Tue, Wed, etc.)
        boys_start_row = 14     # Row 14: First BOYS data row
        girls_start_row = 36    # Row 36: First GIRLS data row
        name_column = 2         # Column B for FULL NAME
        first_day_column = 4    # Column D where day 1 starts (Column D = 4)

        # Helper function to unmerge and write to a cell
        def unmerge_and_write(ws, row, col, value, alignment=None):
            """FORCE unmerge cell if needed and write value."""
            from openpyxl.cell.cell import MergedCell
            
            cell_coord = ws.cell(row=row, column=col).coordinate
            
            for merged_range in list(ws.merged_cells.ranges):
                if cell_coord in merged_range:
                    ws.unmerge_cells(str(merged_range))
                    print(f"  🔓 Unmerged {merged_range}")
                    break
            
            cell = ws.cell(row=row, column=col)
            if isinstance(cell, MergedCell):
                del ws._cells[(row, col)]
                cell = ws.cell(row=row, column=col)
            
            try:
                cell.value = value
                if alignment:
                    cell.alignment = alignment
            except AttributeError as e:
                print(f"  ❌ Error writing to {cell_coord}: {e}")
            
            return cell

        # Get number of days in the month
        days_in_month = monthrange(year, month)[1]
        print(f"📅 Days in {month_name} {year}: {days_in_month}")

        # Build day-to-column mapping - ONLY WEEKDAYS (Mon-Fri)
        day_columns = {}  # {day_number: column_index}
        from datetime import date

        print("\n📅 Filling weekday calendar headers (only Mon-Fri)...")
        current_col = first_day_column  # Start at column D

        for day in range(1, days_in_month + 1):
            current_date = date(year, month, day)
            day_of_week = current_date.weekday()  # 0=Monday, 6=Sunday

            # ONLY process weekdays (Monday=0 to Friday=4)
            if day_of_week < 5:  # Weekday check FIRST
                day_columns[day] = current_col

                # Fill date in row 11
                unmerge_and_write(ws, date_row, current_col, day, center_alignment)

                # Fill day name in row 12 (aligned with calendar)
                day_name = day_names_short[day_of_week]
                unmerge_and_write(ws, day_row, current_col, day_name, center_alignment)

                print(f"  Day {day:2d} ({current_date.strftime('%Y-%m-%d')}): {day_name} at column {current_col}")
                current_col += 1  # Move to next column only for weekdays
            else:
                # Weekend - just log and skip
                day_name_full = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][day_of_week]
                print(f"  Day {day:2d} ({current_date.strftime('%Y-%m-%d')}): {day_name_full} WEEKEND - SKIPPED")

        print(f"✓ Filled {len(day_columns)} weekday columns")

        # Helper function to check if cell is merged
        def is_merged_cell(ws, row, col):
            """Check if a cell is part of a merged range"""
            from openpyxl.cell.cell import MergedCell
            cell = ws.cell(row=row, column=col)
            return isinstance(cell, MergedCell)

        # Helper function to fill attendance for a list of students
        def fill_student_attendance(students_list, start_row):
            filled_count = 0
            for idx, name in enumerate(students_list):
                row_num = start_row + idx
                print(f"  Processing student: {name} at row {row_num}")

                # Write FULL NAME to Column B
                unmerge_and_write(ws, row_num, name_column, name, left_alignment)

                # Fill attendance ONLY for weekdays (skip weekends)
                for day, col_idx in day_columns.items():
                    # Skip future dates
                    if year == current_year and month == current_month and day > current_day:
                        continue

                    try:
                        # Skip merged cells
                        if is_merged_cell(ws, row_num, col_idx):
                            print(f"    ⏭️ Skipping merged cell at row {row_num}, col {col_idx}")
                            continue

                        cell = ws.cell(row=row_num, column=col_idx)

                        # Get attendance status
                        has_am = attendance_data[name]['days'][day]['am']
                        has_pm = attendance_data[name]['days'][day]['pm']

                        # Clear existing content and reset formatting
                        cell.value = None
                        cell.fill = PatternFill(fill_type=None)
                        cell.font = Font()
                        cell.alignment = center_alignment

                        # Apply attendance marking logic
                        # ABSENT - neither AM nor PM present
                        if not has_am and not has_pm:
                            cell.fill = red_fill
                            cell.alignment = center_alignment
                            filled_count += 1

                        # FULL DAY PRESENT - both AM and PM
                        elif has_am and has_pm:
                            cell.fill = green_fill
                            cell.alignment = center_alignment
                            filled_count += 1

                        # HALF DAY PRESENT - TRIANGLES
                        # AM only = ◤ (Middle + Justify)
                        elif has_am and not has_pm:
                            cell.value = "◤"
                            cell.font = triangle_font
                            cell.alignment = am_triangle_alignment
                            filled_count += 1
                            print(f"    ✓ AM triangle (◤) for day {day}: Middle+Justify")

                        # PM only = ◢ (Middle + Left)
                        elif has_pm and not has_am:
                            cell.value = "◢"
                            cell.font = triangle_font
                            cell.alignment = pm_triangle_alignment
                            filled_count += 1
                            print(f"    ✓ PM triangle (◢) for day {day}: Middle+Left")

                    except Exception as e:
                        print(f"    ❌ Error filling day {day}: {e}")

            return filled_count

        # Fill BOYS section (starting at row 14)
        print(f"\n👦 Filling boys section starting at row {boys_start_row}")
        boys_filled = fill_student_attendance(boys, boys_start_row)
        print(f"✓ Filled {boys_filled} cells for boys")

        # Fill GIRLS section (starting at row 36)
        print(f"\n👧 Filling girls section starting at row {girls_start_row}")
        girls_filled = fill_student_attendance(girls, girls_start_row)
        print(f"✓ Filled {girls_filled} cells for girls")

        # Save the workbook to a BytesIO buffer
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        # Generate filename with month name
        filename = f"SF2_{month_name}_{year}_{teacher_profile.section.replace(' ', '_')}.xlsx"
        print(f"\n✅ SF2 generated successfully: {filename}")
        print(f"📊 Total cells filled: {boys_filled + girls_filled}")

        # Return file response
        return FileResponse(
            buffer,
            as_attachment=True,
            filename=filename,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except TeacherProfile.DoesNotExist:
        return Response(
            {"error": "Teacher profile not found."},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        # Log the full error for debugging
        import traceback
        error_trace = traceback.format_exc()
        print("=" * 80)
        print("SF2 Generation Error:")
        print(error_trace)
        print("=" * 80)
        return Response(
            {"error": f"Failed to generate SF2 Excel: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

from .models import ScanPhoto
from .serializers import ScanPhotoSerializer

# ==========================
# SAVE SCAN PHOTO (POST)
# ==========================
class ScanPhotoView(APIView):
    """Save photos captured during scans"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            serializer = ScanPhotoSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(teacher=teacher_profile)
                return Response(
                    {"message": "Photo saved successfully"},
                    status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except TeacherProfile.DoesNotExist:
            return Response(
                {"error": "Teacher profile not found"},
                status=status.HTTP_404_NOT_FOUND
            )

# ==========================
# GET SCAN PHOTOS (GET)
# ==========================
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_scan_photos(request):
    """Get all scan photos for the authenticated teacher"""
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
        photos = ScanPhoto.objects.filter(
            teacher=teacher_profile
        ).order_by('-timestamp')
        serializer = ScanPhotoSerializer(photos, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except TeacherProfile.DoesNotExist:
        return Response(
            {"error": "Teacher profile not found"},
            status=status.HTTP_404_NOT_FOUND
        )
