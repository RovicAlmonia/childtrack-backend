# views.py
from django.contrib.auth import authenticate
from django.db import IntegrityError
from django.http import FileResponse
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
from django.http import FileResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Alignment, Font, Border, Side
from datetime import datetime, date
from collections import defaultdict
from calendar import monthrange
import io
import re

# -----------------------------
# TEACHER REGISTRATION (Public)
# -----------------------------
class RegisterView(generics.CreateAPIView):
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

# -----------------------------
# TEACHER LOGIN (Public)
# -----------------------------
class LoginView(APIView):
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

# -----------------------------
# ATTENDANCE VIEWS
# -----------------------------
class AttendanceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            teacher_profile = TeacherProfile.objects.filter(user=request.user).first()
            if not teacher_profile:
                return Response({"error": "Teacher profile not found"}, status=status.HTTP_404_NOT_FOUND)

            date = request.query_params.get('date')
            student = request.query_params.get('student')
            status_filter = request.query_params.get('status')

            queryset = Attendance.objects.filter(teacher=teacher_profile)
            if date:
                queryset = queryset.filter(date=date)
            if student:
                queryset = queryset.filter(student_name__icontains=student)
            if status_filter:
                queryset = queryset.filter(status=status_filter)

            attendances = queryset.order_by('-date', '-timestamp')
            serializer = AttendanceSerializer(attendances, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response({"error": f"Error fetching attendance: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)

            data = request.data.copy()
            qr_data = data.get('qr_data', '')

            if qr_data:
                try:
                    qr_json = json.loads(qr_data)
                    data['student_lrn'] = qr_json.get('lrn', '')
                    if not data.get('student_name'):
                        data['student_name'] = qr_json.get('student', 'Unknown')
                except json.JSONDecodeError:
                    pass

            if not data.get('date'):
                data['date'] = datetime.now().date()

            timestamp = datetime.now()
            data['session'] = 'AM' if timestamp.hour < 12 else 'PM'

            serializer = AttendanceSerializer(data=data)
            if serializer.is_valid():
                serializer.save(teacher=teacher_profile)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except TeacherProfile.DoesNotExist:
            return Response({"error": "Teacher profile not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AttendanceDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, pk):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            attendance = Attendance.objects.get(pk=pk, teacher=teacher_profile)
            serializer = AttendanceSerializer(attendance, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Attendance.DoesNotExist:
            return Response({"error": "Attendance record not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            attendance = Attendance.objects.get(pk=pk, teacher=teacher_profile)
            attendance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Attendance.DoesNotExist:
            return Response({"error": "Attendance record not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# -----------------------------
# ABSENCE VIEWS
# -----------------------------
class AbsenceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            absences = Absence.objects.filter(teacher=teacher_profile).order_by('-date')
            serializer = AbsenceSerializer(absences, many=True)
            return Response(serializer.data)
        except TeacherProfile.DoesNotExist:
            return Response({"error": "Teacher profile not found"}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            serializer = AbsenceSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(teacher=teacher_profile)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except TeacherProfile.DoesNotExist:
            return Response({"error": "Teacher profile not found"}, status=status.HTTP_404_NOT_FOUND)

class AbsenceDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, pk):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            absence = Absence.objects.get(pk=pk, teacher=teacher_profile)
            serializer = AbsenceSerializer(absence, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Absence.DoesNotExist:
            return Response({"error": "Absence not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            absence = Absence.objects.get(pk=pk, teacher=teacher_profile)
            absence.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Absence.DoesNotExist:
            return Response({"error": "Absence not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# -----------------------------
# DROPOUT VIEWS
# -----------------------------
class DropoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            dropouts = Dropout.objects.filter(teacher=teacher_profile).order_by('-date')
            serializer = DropoutSerializer(dropouts, many=True)
            return Response(serializer.data)
        except TeacherProfile.DoesNotExist:
            return Response({"error": "Teacher profile not found"}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            serializer = DropoutSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(teacher=teacher_profile)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except TeacherProfile.DoesNotExist:
            return Response({"error": "Teacher profile not found"}, status=status.HTTP_404_NOT_FOUND)

class DropoutDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, pk):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            dropout = Dropout.objects.get(pk=pk, teacher=teacher_profile)
            serializer = DropoutSerializer(dropout, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Dropout.DoesNotExist:
            return Response({"error": "Dropout not found"}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            dropout = Dropout.objects.get(pk=pk, teacher=teacher_profile)
            dropout.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Dropout.DoesNotExist:
            return Response({"error": "Dropout not found"}, status=status.HTTP_404_NOT_FOUND)

# -----------------------------
# UNAUTHORIZED PERSON VIEWS
# -----------------------------
class UnauthorizedPersonView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            persons = UnauthorizedPerson.objects.filter(teacher=teacher_profile).order_by('-timestamp')
            serializer = UnauthorizedPersonSerializer(persons, many=True)
            return Response(serializer.data)
        except TeacherProfile.DoesNotExist:
            return Response({"error": "Teacher profile not found"}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            serializer = UnauthorizedPersonSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(teacher=teacher_profile)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except TeacherProfile.DoesNotExist:
            return Response({"error": "Teacher profile not found"}, status=status.HTTP_404_NOT_FOUND)

class UnauthorizedPersonDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, pk):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            person = UnauthorizedPerson.objects.get(pk=pk, teacher=teacher_profile)
            serializer = UnauthorizedPersonSerializer(person, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except UnauthorizedPerson.DoesNotExist:
            return Response({"error": "Person not found"}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            person = UnauthorizedPerson.objects.get(pk=pk, teacher=teacher_profile)
            person.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except UnauthorizedPerson.DoesNotExist:
            return Response({"error": "Person not found"}, status=status.HTTP_404_NOT_FOUND)

# -----------------------------
# PUBLIC ATTENDANCE LIST
# -----------------------------
class PublicAttendanceListView(generics.ListAPIView):
    queryset = Attendance.objects.all().order_by('-timestamp')
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

# -----------------------------
# SF2 EXCEL GENERATION - Fixed Version
# -----------------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_sf2_excel(request):
    """
    Generate SF2 Excel Report with full year attendance data
    
    Marking system:
    - AM Present: Upper triangle ▲ (green)
    - PM Present: Lower triangle ▼ (green)
    - Full Day Present: Solid green fill
    - Absent: Solid red fill
    - No data (future dates): Empty cell
    
    Request format:
    - template_file: Excel template file (multipart/form-data)
    - year: Year to generate report for (optional, defaults to current year)
    """
    try:
        # Get authenticated teacher profile
        teacher_profile = TeacherProfile.objects.get(user=request.user)

        # Get uploaded Excel template
        template_file = request.FILES.get('template_file')
        if not template_file:
            return Response(
                {"error": "Please upload an SF2 template file (.xlsx)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate file extension
        if not template_file.name.lower().endswith(('.xlsx', '.xls')):
            return Response(
                {"error": "Invalid file format. Please upload an Excel file (.xlsx or .xls)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Load workbook from uploaded template
        try:
            wb = load_workbook(template_file)
        except Exception as e:
            return Response(
                {"error": f"Failed to load Excel template: {str(e)}. Ensure the file is a valid Excel file."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get year parameter (default to current year)
        try:
            target_year = int(request.POST.get('year', datetime.now().year))
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid year parameter. Must be a valid integer."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate year range
        current_year = datetime.now().year
        if target_year < 2020 or target_year > current_year + 1:
            return Response(
                {"error": f"Year must be between 2020 and {current_year + 1}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Month names mapping (must match sheet names in template)
        MONTH_NAMES = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", 
                       "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

        # Fetch ALL attendance records for this teacher for the target year
        attendances = Attendance.objects.filter(
            teacher=teacher_profile,
            date__year=target_year
        ).select_related('teacher').order_by('date', 'timestamp')

        print(f"Found {attendances.count()} attendance records for year {target_year}")

        # Build attendance data structure
        # Format: attendance_dict[student_key][month_name][day] = {'am': bool, 'pm': bool}
        attendance_dict = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {'am': False, 'pm': False})))
        
        # Track all unique students
        students_map = {}  # student_key -> (lrn, name)
        
        for att in attendances:
            # Use LRN as primary key, fallback to name if no LRN
            student_key = att.student_lrn.strip() if att.student_lrn else att.student_name.strip()
            
            # Store student info
            if student_key not in students_map:
                students_map[student_key] = (att.student_lrn or '', att.student_name)
            
            # Get month name and day
            month_idx = att.date.month - 1  # 0-based index
            month_name = MONTH_NAMES[month_idx]
            day = att.date.day
            
            # Determine session (prioritize session field, fallback to timestamp)
            if att.session:
                session = att.session.upper().strip()
            else:
                # Use timestamp to determine AM/PM
                session = 'AM' if att.timestamp.hour < 12 else 'PM'
            
            # Mark attendance ONLY if NOT absent
            status_lower = att.status.lower()
            if status_lower not in ['absent', 'absence']:
                if session == 'AM':
                    attendance_dict[student_key][month_name][day]['am'] = True
                elif session == 'PM':
                    attendance_dict[student_key][month_name][day]['pm'] = True
            
            print(f"Processed: {student_key} - {month_name} {day} - {session} - {att.status}")

        # Sort students alphabetically by name
        students_sorted = sorted(students_map.items(), key=lambda x: x[1][1].lower())
        
        print(f"Total unique students: {len(students_sorted)}")

        # Define cell styles
        RED_FILL = PatternFill(start_color='FF6B6B', end_color='FF6B6B', fill_type='solid')
        GREEN_FILL = PatternFill(start_color='90EE90', end_color='90EE90', fill_type='solid')
        GREEN_FONT = Font(color="228B22", size=14, bold=True)
        BORDER_STYLE = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

        # Current date for filtering future dates
        today = date.today()

        # Process each month sheet
        for month_idx, month_name in enumerate(MONTH_NAMES, start=1):
            if month_name not in wb.sheetnames:
                print(f"Warning: Sheet '{month_name}' not found in template. Skipping...")
                continue

            ws = wb[month_name]
            print(f"\nProcessing sheet: {month_name}")

            # TEMPLATE CONFIGURATION - ADJUST THESE VALUES TO MATCH YOUR TEMPLATE
            DATE_HEADER_ROW = 11      # Row where day numbers (1, 2, 3...) are displayed
            STUDENT_START_ROW = 14    # First row where student data begins
            LRN_COLUMN = 3           # Column index for LRN
            NAME_COLUMN = 2           # Column index for student name
            FIRST_DAY_COLUMN = 4      # Column where day 1 starts

            # Detect day columns by reading the header row
            day_columns = {}  # day_number -> column_index
            for col_idx in range(FIRST_DAY_COLUMN, FIRST_DAY_COLUMN + 31):
                try:
                    cell_value = ws.cell(row=DATE_HEADER_ROW, column=col_idx).value
                    if cell_value:
                        # Extract day number from cell (handles formats like "1", "01", "Day 1", etc.)
                        match = re.search(r'(\d+)', str(cell_value).strip())
                        if match:
                            day_num = int(match.group(1))
                            if 1 <= day_num <= 31:
                                day_columns[day_num] = col_idx
                                print(f"  Detected day {day_num} at column {col_idx}")
                except Exception as e:
                    print(f"  Error reading column {col_idx}: {e}")
                    continue

            if not day_columns:
                print(f"  WARNING: No day columns detected for {month_name}. Check DATE_HEADER_ROW and FIRST_DAY_COLUMN.")
                continue

            # Get number of days in this month
            days_in_month = monthrange(target_year, month_idx)[1]
            print(f"  Days in {month_name} {target_year}: {days_in_month}")

            # Fill student data
            for idx, (student_key, (lrn, name)) in enumerate(students_sorted):
                row_num = STUDENT_START_ROW + idx
                
                # Write student name and LRN
                name_cell = ws.cell(row=row_num, column=NAME_COLUMN)
                name_cell.value = name
                name_cell.alignment = Alignment(horizontal='left', vertical='center')
                
                if lrn:
                    lrn_cell = ws.cell(row=row_num, column=LRN_COLUMN)
                    lrn_cell.value = lrn
                    lrn_cell.alignment = Alignment(horizontal='center', vertical='center')

                # Process each day in the month
                for day in range(1, days_in_month + 1):
                    if day not in day_columns:
                        continue
                    
                    col_idx = day_columns[day]
                    cell = ws.cell(row=row_num, column=col_idx)
                    
                    # Reset cell formatting
                    cell.value = None
                    cell.fill = PatternFill()
                    cell.font = Font()
                    cell.alignment = Alignment(horizontal='center', vertical='center')
                    cell.border = BORDER_STYLE

                    # Check if date is in the future
                    current_date = date(target_year, month_idx, day)
                    if current_date > today:
                        # Future date - leave blank
                        continue

                    # Get attendance status for this day
                    has_am = attendance_dict[student_key][month_name][day]['am']
                    has_pm = attendance_dict[student_key][month_name][day]['pm']

                    # MARKING LOGIC
                    if has_am and has_pm:
                        # Full day present - solid green fill
                        cell.fill = GREEN_FILL
                    elif has_am and not has_pm:
                        # AM only - upper triangle
                        cell.value = "▲"
                        cell.font = GREEN_FONT
                    elif has_pm and not has_am:
                        # PM only - lower triangle
                        cell.value = "▼"
                        cell.font = GREEN_FONT
                    else:
                        # Neither AM nor PM - mark as absent (red fill)
                        cell.fill = RED_FILL

            print(f"  Completed {month_name} with {len(students_sorted)} students")

        # Save workbook to BytesIO buffer
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        section_safe = re.sub(r'[^\w\-_]', '_', teacher_profile.section)
        filename = f"SF2_Report_{section_safe}_{target_year}_{timestamp}.xlsx"

        print(f"\nGenerated SF2 report: {filename}")

        # Return file as response
        return FileResponse(
            buffer,
            as_attachment=True,
            filename=filename,
            content_type='application/vnd.openxmlformats-officedocket.spreadsheetml.sheet'
        )

    except TeacherProfile.DoesNotExist:
        return Response(
            {"error": "Teacher profile not found. Please ensure you are logged in."},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        # Log the full error for debugging
        import traceback
        error_trace = traceback.format_exc()
        print("=" * 80)
        print("SF2 GENERATION ERROR:")
        print(error_trace)
        print("=" * 80)
        
        return Response(
            {"error": f"Failed to generate SF2 report: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
