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
from datetime import datetime
from collections import defaultdict
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
# SF2 EXCEL GENERATION - Fixed Version
# -----------------------------
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_sf2_excel(request):
    """
    Generate SF2 Excel with:
      - AM (Morning): upper-left green triangle (▲)
      - PM (Afternoon): lower-right green triangle (▼)
      - Full Day Present: solid green fill
      - Absent: solid red fill
    
    Request should include:
      - template_file: uploaded Excel template (FILE)
      - month: integer 1-12 (optional, defaults to current month)
      - year: integer (optional, defaults to current year)
    """
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)

        # Get uploaded Excel template
        template_file = request.FILES.get('template_file')
        if not template_file:
            return Response(
                {"error": "Please upload an SF2 template file."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Load workbook
        try:
            wb = load_workbook(template_file)
        except Exception as e:
            return Response(
                {"error": f"Failed to load Excel template: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get month and year parameters
        try:
            month = int(request.POST.get('month', datetime.now().month))
            year = int(request.POST.get('year', datetime.now().year))
        except ValueError:
            return Response(
                {"error": "Invalid month or year parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate month
        if month < 1 or month > 12:
            return Response(
                {"error": "Month must be between 1 and 12"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Month names mapping
        month_names = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", 
                      "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

        # Fetch all attendance records for this teacher
        attendances = Attendance.objects.filter(
            teacher=teacher_profile,
            date__year=year
        ).order_by('date', 'timestamp')

        # Prepare attendance dictionary
        # Structure: attendance_data[student_key][month_name][day] = {'am': bool, 'pm': bool}
        attendance_data = defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(lambda: {'am': False, 'pm': False})
            )
        )
        students_set = set()

        for att in attendances:
            # Add student to set
            students_set.add((att.student_lrn or '', att.student_name))
            
            # Use LRN as key if available, otherwise use name
            student_key = att.student_lrn if att.student_lrn else att.student_name
            
            # Get month name
            month_name = month_names[att.date.month - 1]
            day = att.date.day
            
            # Determine session (use the session field if available)
            if att.session:
                session = att.session.upper()
            else:
                # Fallback to timestamp hour if session not set
                session = 'AM' if att.timestamp.hour < 12 else 'PM'

            # Only mark as present if status is not 'Absent'
            if att.status and att.status.lower() != 'absent':
                if session == 'AM':
                    attendance_data[student_key][month_name][day]['am'] = True
                elif session == 'PM':
                    attendance_data[student_key][month_name][day]['pm'] = True

        # Sort students by name
        students = sorted(list(students_set), key=lambda x: x[1])

        # Current date for limiting future dates
        now = datetime.now()
        current_month = month_names[now.month - 1]
        current_day = now.day
        current_year = now.year

        # Define fills
        red_fill = PatternFill(start_color='FF7F7F', end_color='FF7F7F', fill_type='solid')
        green_fill = PatternFill(start_color='43A047', end_color='43A047', fill_type='solid')
        green_font = Font(color="43A047", size=11, bold=True)

        # Process each month sheet
        for month_name in month_names:
            if month_name not in wb.sheetnames:
                print(f"Warning: Sheet '{month_name}' not found in template")
                continue

            ws = wb[month_name]
            
            # Configuration: adjust these values based on your template
            date_header_row = 10  # Row where dates are displayed (1, 2, 3, ...)
            start_row = 13        # First row for student data
            lrn_column = 1        # Column for LRN
            name_column = 2       # Column for student name
            first_day_column = 7  # Column where day 1 starts

            # Find columns representing each day (1-31)
            day_columns = {}
            for col_idx in range(first_day_column, 38):  # Check up to column 38
                cell_value = ws.cell(row=date_header_row, column=col_idx).value
                if cell_value:
                    # Try to extract day number
                    match = re.match(r'(\d+)', str(cell_value).strip())
                    if match:
                        day_num = int(match.group(1))
                        if 1 <= day_num <= 31:
                            day_columns[day_num] = col_idx

            # Fill student data
            for idx, (lrn, name) in enumerate(students):
                row_num = start_row + idx
                
                # Write student name and LRN
                ws.cell(row=row_num, column=name_column, value=name)
                if lrn:
                    ws.cell(row=row_num, column=lrn_column, value=lrn)

                student_key = lrn if lrn else name

                # Fill attendance for each day
                for day, col_idx in day_columns.items():
                    # Skip future dates
                    if year == current_year:
                        if month_name == current_month and day > current_day:
                            continue
                        # Skip months in the future
                        month_idx = month_names.index(month_name) + 1
                        if month_idx > now.month:
                            continue

                    cell = ws.cell(row=row_num, column=col_idx)
                    cell.alignment = Alignment(horizontal='center', vertical='center')
                    
                    # Get attendance status
                    has_am = attendance_data[student_key][month_name][day]['am']
                    has_pm = attendance_data[student_key][month_name][day]['pm']

                    # Clear previous content
                    cell.value = None
                    cell.fill = PatternFill()  # Remove any existing fill
                    cell.font = Font()  # Reset font

                    # ABSENT - full red fill (neither AM nor PM present)
                    if not has_am and not has_pm:
                        cell.fill = red_fill
                        continue

                    # FULL DAY PRESENT - solid green fill
                    if has_am and has_pm:
                        cell.fill = green_fill
                        continue

                    # HALF DAY PRESENT - use Unicode triangles
                    if has_am and not has_pm:
                        # AM only - upper triangle
                        cell.value = "▲"
                        cell.font = green_font
                    elif has_pm and not has_am:
                        # PM only - lower triangle
                        cell.value = "▼"
                        cell.font = green_font

        # Save workbook to BytesIO
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        # Generate filename
        filename = f"SF2_Report_{teacher_profile.section.replace(' ', '_')}_{year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
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
        import traceback
        error_trace = traceback.format_exc()
        print("SF2 Generation Error:")
        print(error_trace)
        return Response(
            {"error": f"Failed to generate SF2 Excel: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
