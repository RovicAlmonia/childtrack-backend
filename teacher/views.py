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
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Alignment, Font
from openpyxl.drawing.fill import GradientFillProperties, GradientStop
from datetime import datetime
from collections import defaultdict
from calendar import monthrange
import io
import json
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
# SF2 EXCEL GENERATION - Complete Implementation
# -----------------------------
# Replace the generate_sf2_excel function in views.py with this corrected version
# Replace the generate_sf2_excel function in views.py with this corrected version

# Replace the generate_sf2_excel function in views.py with this corrected version

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_sf2_excel(request):
    """
    Generate SF2 Excel report with attendance data for a specific month.
    
    Visual Legend:
    - AM Present (Morning): Upper-left green triangle (▲)
    - PM Present (Afternoon): Lower-right green triangle (▼)
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

        # Month names for sheet selection
        month_names = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", 
                      "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

        # FIXED: Fetch attendance records for the SPECIFIC MONTH only
        attendances = Attendance.objects.filter(
            teacher=teacher_profile,
            date__year=year,
            date__month=month  # Filter by specific month
        ).order_by('date', 'timestamp')

        print(f"📊 Fetching attendance for: {month_names[month-1]} {year}")
        print(f"📝 Found {attendances.count()} attendance records")

        # Build attendance data structure
        # attendance_data[student_key][day] = {'am': bool, 'pm': bool}
        attendance_data = defaultdict(
            lambda: defaultdict(lambda: {'am': False, 'pm': False})
        )
        
        # Set to collect all unique students
        students_set = set()

        # Process each attendance record
        for att in attendances:
            # Add student to the set (LRN, Name)
            students_set.add((att.student_lrn or '', att.student_name))
            
            # Use LRN as primary key, fallback to name if LRN is empty
            student_key = att.student_lrn if att.student_lrn else att.student_name
            
            day = att.date.day
            
            # Determine session (AM/PM)
            if att.session:
                session = att.session.upper()
            else:
                # Fallback to timestamp hour if session field is not set
                session = 'AM' if att.timestamp.hour < 12 else 'PM'

            # Mark attendance only if status is NOT 'Absent'
            # This means Present, Late, Drop-off, Pick-up all count as present
            if att.status and att.status.lower() != 'absent':
                if session == 'AM':
                    attendance_data[student_key][day]['am'] = True
                elif session == 'PM':
                    attendance_data[student_key][day]['pm'] = True

        # Sort students alphabetically by name
        students = sorted(list(students_set), key=lambda x: x[1])
        print(f"👥 Processing {len(students)} students")

        # Current date information (to avoid marking future dates)
        now = datetime.now()
        current_day = now.day
        current_year = now.year
        current_month = now.month

        # Define cell styling
        red_fill = PatternFill(start_color='FF7F7F', end_color='FF7F7F', fill_type='solid')
        green_fill = PatternFill(start_color='43A047', end_color='43A047', fill_type='solid')
        green_font = Font(color="43A047", size=11, bold=True)
        center_alignment = Alignment(horizontal='center', vertical='center')

        # FIXED: Use the actual sheet name from the template
        # Most SF2 templates have a single sheet, not separate monthly sheets
        if len(wb.sheetnames) > 0:
            sheet_name = wb.sheetnames[0]  # Use the first sheet
            ws = wb[sheet_name]
            print(f"📄 Processing sheet: {sheet_name}")
        else:
            return Response(
                {"error": "No sheets found in template"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        month_name = month_names[month - 1]
        print(f"📅 Filling data for: {month_name} {year}")
        
        # Helper function to safely write to cells (including merged cells)
        def safe_write_cell(worksheet, cell_ref, value):
            """Safely write to a cell, handling merged cells"""
            try:
                cell = worksheet[cell_ref]
                # Check if this cell is part of a merged cell range
                for merged_range in worksheet.merged_cells.ranges:
                    if cell.coordinate in merged_range:
                        # Write to the top-left cell of the merged range
                        min_col, min_row, max_col, max_row = merged_range.bounds
                        top_left_cell = worksheet.cell(row=min_row, column=min_col)
                        top_left_cell.value = value
                        return
                # If not merged, write directly
                cell.value = value
            except Exception as e:
                print(f"⚠️ Could not write to {cell_ref}: {e}")
        
        # Fill in template metadata based on SF2 template structure
        # Row 6: School ID (D6), School Year (F6), Month (AI6)
        safe_write_cell(ws, 'D6', "")  # School ID - You can add this to teacher profile if needed
        safe_write_cell(ws, 'F6', f"{year}-{year+1}")  # School Year (e.g., "2025-2026")
        safe_write_cell(ws, 'AI6', month_name)  # Month field
        
        # Row 8: Grade Level (L8), Section (AI8)
        # Extract grade from section (e.g., "grade 8 Wonder" -> "8")
        grade_match = re.search(r'grade\s*(\d+)', teacher_profile.section, re.IGNORECASE)
        if grade_match:
            safe_write_cell(ws, 'L8', grade_match.group(1))  # Just the grade number
        
        # Extract section name (e.g., "grade 8 Wonder" -> "Wonder")
        section_match = re.search(r'grade\s*\d+\s*(.+)', teacher_profile.section, re.IGNORECASE)
        if section_match:
            safe_write_cell(ws, 'AI8', section_match.group(1).strip())  # Section name
        else:
            safe_write_cell(ws, 'AI8', teacher_profile.section)  # Fallback to full section
        
        print(f"📋 Template filled: Year={year}-{year+1}, Month={month_name}")
        
        # Template Configuration based on SF2 template structure
        # Row 10: "LEARNER'S NAME" header and date headers
        # Row 11: "(Last Name, First Name, Middle Name)" subheader
        date_header_row = 10      # Row where dates (1, 2, 3, ...) are displayed
        start_row = 15            # First row where student data begins (row 15 in template)
        name_column = 3           # Column C for student name (Last Name, First Name, Middle)
        first_day_column = 4      # Column D where day 1 starts

        # Find all day columns by scanning the date header row
        day_columns = {}
        for col_idx in range(first_day_column, 38):  # Check columns up to 38
            cell_value = ws.cell(row=date_header_row, column=col_idx).value
            if cell_value:
                # Try to extract day number from cell
                match = re.match(r'(\d+)', str(cell_value).strip())
                if match:
                    day_num = int(match.group(1))
                    if 1 <= day_num <= 31:
                        day_columns[day_num] = col_idx

        print(f"📅 Found {len(day_columns)} day columns in template")

        # Fill in student attendance data
        for idx, (lrn, name) in enumerate(students):
            row_num = start_row + idx
            
            # Write student name in "Last Name, First Name, Middle Name" format
            # The template expects full name in column C
            ws.cell(row=row_num, column=name_column, value=name)

            # Use LRN as key if available, otherwise use name
            student_key = lrn if lrn else name

            # Fill attendance for each day in the month
            for day, col_idx in day_columns.items():
                # Skip future dates only if we're generating for current month/year
                if year == current_year and month == current_month and day > current_day:
                    continue

                # Get the cell for this day
                cell = ws.cell(row=row_num, column=col_idx)
                cell.alignment = center_alignment
                
                # Get attendance status for this day
                has_am = attendance_data[student_key][day]['am']
                has_pm = attendance_data[student_key][day]['pm']

                # Clear any existing content
                cell.value = None
                cell.fill = PatternFill()  # Reset fill
                cell.font = Font()         # Reset font

                # Apply attendance marking logic
                # ABSENT - neither AM nor PM present
                if not has_am and not has_pm:
                    cell.fill = red_fill
                    continue

                # FULL DAY PRESENT - both AM and PM
                if has_am and has_pm:
                    cell.fill = green_fill
                    continue

                # HALF DAY PRESENT - either AM or PM
                if has_am and not has_pm:
                    # AM only - upper triangle (▲)
                    cell.value = "▲"
                    cell.font = green_font
                elif has_pm and not has_am:
                    # PM only - lower triangle (▼)
                    cell.value = "▼"
                    cell.font = green_font

        # Save the workbook to a BytesIO buffer
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        # Generate filename with month name
        filename = f"SF2_{month_name}_{year}_{teacher_profile.section.replace(' ', '_')}.xlsx"
        
        print(f"✅ SF2 generated successfully: {filename}")
        
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
