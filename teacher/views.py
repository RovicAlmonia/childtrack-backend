# views.py
from django.contrib.auth import authenticate
from django.db import IntegrityError
from django.http import FileResponse, HttpResponse
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
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import io
import json
from datetime import datetime
from collections import defaultdict
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
            if not request.user.is_authenticated:
                return Response(
                    {"error": "User not authenticated"}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )

            teacher_profile = TeacherProfile.objects.filter(user=request.user).first()
            if not teacher_profile:
                return Response(
                    {"error": "Teacher profile not found"}, 
                    status=status.HTTP_404_NOT_FOUND
                )

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
            return Response(
                {"error": f"Error fetching attendance: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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
            return Response(
                {"error": "Teacher profile not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
            return Response(
                {"error": "Attendance record not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request, pk):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            attendance = Attendance.objects.get(pk=pk, teacher=teacher_profile)
            attendance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Attendance.DoesNotExist:
            return Response(
                {"error": "Attendance record not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
            return Response(
                {"error": "Teacher profile not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    def post(self, request):
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
            return Response(
                {"error": "Absence not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, pk):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            absence = Absence.objects.get(pk=pk, teacher=teacher_profile)
            absence.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Absence.DoesNotExist:
            return Response(
                {"error": "Absence not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
            return Response(
                {"error": "Teacher profile not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    def post(self, request):
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
            return Response(
                {"error": "Dropout not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    def delete(self, request, pk):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            dropout = Dropout.objects.get(pk=pk, teacher=teacher_profile)
            dropout.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Dropout.DoesNotExist:
            return Response(
                {"error": "Dropout not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )


# -----------------------------
# UNAUTHORIZED PERSON VIEWS
# -----------------------------
class UnauthorizedPersonView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
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
            return Response(
                {"error": "Person not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    def delete(self, request, pk):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            person = UnauthorizedPerson.objects.get(pk=pk, teacher=teacher_profile)
            person.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except UnauthorizedPerson.DoesNotExist:
            return Response(
                {"error": "Person not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )


# -----------------------------
# PUBLIC ATTENDANCE LIST
# -----------------------------
class PublicAttendanceListView(generics.ListAPIView):
    queryset = Attendance.objects.all().order_by('-timestamp')
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []


# -----------------------------
# SF2 EXCEL GENERATION - SIMPLIFIED & WORKING
# -----------------------------
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_sf2_excel(request):
    """
    Generate SF2 Excel report - SIMPLIFIED VERSION
    Uses pure Excel styling instead of PIL images for better reliability
    """
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
        
        # Get template file
        template_file = request.FILES.get('template_file')
        if not template_file:
            return Response(
                {"error": "Please upload an SF2 template file"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        print(f"📄 Loading template: {template_file.name}")
        
        # Get month and year from request
        month = int(request.POST.get('month', datetime.now().month))
        year = int(request.POST.get('year', datetime.now().year))
        
        print(f"📅 Generating SF2 for: {month}/{year}")
        
        # Load workbook
        try:
            wb = load_workbook(template_file)
            print(f"✅ Workbook loaded. Sheets: {wb.sheetnames}")
        except Exception as e:
            print(f"❌ Error loading workbook: {e}")
            return Response(
                {"error": f"Invalid Excel template: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Month names
        month_names = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", 
                      "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        
        # Fetch attendance records
        attendances = Attendance.objects.filter(
            teacher=teacher_profile
        ).order_by('date', 'timestamp')
        
        print(f"📊 Found {attendances.count()} attendance records")
        
        # Extract unique students
        students_set = set()
        for att in attendances:
            students_set.add((att.student_lrn or '', att.student_name))
        
        students = sorted(list(students_set), key=lambda x: x[1])
        print(f"👥 Found {len(students)} unique students")
        
        # Organize attendance data
        attendance_data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {'am': False, 'pm': False})))
        
        for att in attendances:
            student_key = att.student_lrn or att.student_name
            month_name = month_names[att.date.month - 1]
            day = att.date.day
            
            session = att.session.upper() if att.session else ('AM' if att.timestamp.hour < 12 else 'PM')
            
            if att.status.lower() not in ['absent']:
                if session == 'AM':
                    attendance_data[student_key][month_name][day]['am'] = True
                else:
                    attendance_data[student_key][month_name][day]['pm'] = True
        
        # Define Excel styles
        green_fill = PatternFill(start_color='43A047', end_color='43A047', fill_type='solid')
        light_green_fill = PatternFill(start_color='C8E6C9', end_color='C8E6C9', fill_type='solid')
        red_fill = PatternFill(start_color='FF7F7F', end_color='FF7F7F', fill_type='solid')
        
        thin_border = Border(
            left=Side(style='thin', color='000000'),
            right=Side(style='thin', color='000000'),
            top=Side(style='thin', color='000000'),
            bottom=Side(style='thin', color='000000')
        )
        
        diagonal_border = Border(
            left=Side(style='thin', color='000000'),
            right=Side(style='thin', color='000000'),
            top=Side(style='thin', color='000000'),
            bottom=Side(style='thin', color='000000'),
            diagonal=Side(style='dashed', color='000000'),
            diagonalUp=True
        )
        
        white_font = Font(color='FFFFFF', size=8, bold=True)
        black_font = Font(color='000000', size=10)
        
        # Current date
        now = datetime.now()
        current_month = month_names[now.month - 1]
        current_day = now.day
        
        # Process each month
        for month_name in month_names:
            if month_name not in wb.sheetnames:
                continue
            
            ws = wb[month_name]
            month_index = month_names.index(month_name)
            
            # Skip future months
            if month_index > now.month - 1:
                continue
            
            print(f"📝 Processing month: {month_name}")
            
            # Find date header row (row 10)
            date_header_row = 10
            
            # Find day columns
            day_columns = {}
            for col_idx in range(7, 38):
                try:
                    cell_value = ws.cell(row=date_header_row, column=col_idx).value
                    if cell_value:
                        match = re.match(r'(\d+)', str(cell_value).strip())
                        if match:
                            day_num = int(match.group(1))
                            if 1 <= day_num <= 31:
                                day_columns[day_num] = col_idx
                except:
                    pass
            
            print(f"  📅 Found {len(day_columns)} day columns")
            
            # Student rows start at row 13
            start_row = 13
            
            # Process students
            for idx, (lrn, name) in enumerate(students):
                row_num = start_row + idx
                
                # Add student name in column B (column 2)
                name_cell = ws.cell(row=row_num, column=2)
                name_cell.value = name
                name_cell.alignment = Alignment(vertical='center', horizontal='left')
                name_cell.font = black_font
                
                # Add LRN in column A (column 1) if available
                if lrn:
                    lrn_cell = ws.cell(row=row_num, column=1)
                    lrn_cell.value = lrn
                    lrn_cell.alignment = Alignment(vertical='center', horizontal='center')
                    lrn_cell.font = black_font
                
                student_key = lrn or name
                
                # Process each day
                for day in range(1, 32):
                    if day not in day_columns:
                        continue
                    
                    col_idx = day_columns[day]
                    
                    # Skip future dates
                    if month_name == current_month and day > current_day:
                        continue
                    
                    cell = ws.cell(row=row_num, column=col_idx)
                    cell.alignment = Alignment(horizontal='center', vertical='center')
                    
                    # Get attendance
                    has_am = attendance_data[student_key][month_name][day]['am']
                    has_pm = attendance_data[student_key][month_name][day]['pm']
                    
                    if has_am or has_pm:
                        # Present - green fill with marker
                        if has_am and has_pm:
                            cell.fill = green_fill
                            cell.value = "✓"
                            cell.font = white_font
                        elif has_am:
                            cell.fill = light_green_fill
                            cell.value = "AM"
                            cell.font = Font(color='1B5E20', size=7, bold=True)
                        else:
                            cell.fill = light_green_fill
                            cell.value = "PM"
                            cell.font = Font(color='1B5E20', size=7, bold=True)
                        
                        cell.border = diagonal_border
                    else:
                        # Absent - red fill with X
                        cell.value = "X"
                        cell.fill = red_fill
                        cell.border = thin_border
                        cell.font = white_font
        
        print("💾 Saving workbook...")
        
        # Save to buffer
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        # Generate filename
        filename = f"SF2_Report_{teacher_profile.section.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        
        print(f"✅ SF2 generated successfully: {filename}")
        
        # Create response
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except TeacherProfile.DoesNotExist:
        print("❌ Teacher profile not found")
        return Response(
            {"error": "Teacher profile not found"}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ SF2 Generation Error:\n{error_trace}")
        return Response(
            {"error": f"Error generating SF2: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# -----------------------------
# DEMO ENDPOINT
# -----------------------------
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def generate_half_triangle_demo(request):
    """Demo endpoint for testing Excel generation"""
    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "SF2 Demo"
        
        # Headers
        ws['A1'] = "Status"
        ws['A1'].font = Font(bold=True, size=12)
        ws['B1'] = "Visual Example"
        ws['B1'].font = Font(bold=True, size=12)
        
        ws.column_dimensions['A'].width = 20
        ws.column_dimensions['B'].width = 15
        
        # Define styles
        green_fill = PatternFill(start_color='43A047', end_color='43A047', fill_type='solid')
        light_green_fill = PatternFill(start_color='C8E6C9', end_color='C8E6C9', fill_type='solid')
        red_fill = PatternFill(start_color='FF7F7F', end_color='FF7F7F', fill_type='solid')
        white_font = Font(color='FFFFFF', size=10, bold=True)
        green_font = Font(color='1B5E20', size=9, bold=True)
        
        diagonal_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin'),
            diagonal=Side(style='dashed', color='000000'),
            diagonalUp=True
        )
        
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Examples
        examples = [
            (2, "Full Day (AM+PM)", green_fill, "✓", white_font, diagonal_border),
            (3, "Morning Only (AM)", light_green_fill, "AM", green_font, diagonal_border),
            (4, "Afternoon Only (PM)", light_green_fill, "PM", green_font, diagonal_border),
            (5, "Absent", red_fill, "X", white_font, thin_border),
        ]
        
        for row, label, fill, value, font, border in examples:
            ws[f'A{row}'] = label
            ws[f'A{row}'].alignment = Alignment(vertical='center')
            
            cell = ws[f'B{row}']
            cell.value = value
            cell.fill = fill
            cell.font = font
            cell.border = border
            cell.alignment = Alignment(horizontal='center', vertical='center')
            ws.row_dimensions[row].height = 25
        
        # Legend
        ws['A7'] = "Legend:"
        ws['A7'].font = Font(bold=True, size=11)
        ws['A8'] = "✓ = Present all day (AM & PM)"
        ws['A9'] = "AM = Present in morning only"
        ws['A10'] = "PM = Present in afternoon only"
        ws['A11'] = "X = Absent"
        
        # Save
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="sf2_demo.xlsx"'
        
        return response
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return Response(
            {"error": f"Error generating demo: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
