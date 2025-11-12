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
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image as ExcelImage
import io
import json
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from collections import defaultdict


# -----------------------------
# TEACHER REGISTRATION (Public)
# -----------------------------
class RegisterView(generics.CreateAPIView):
    """
    Public endpoint for teacher registration.
    Creates a new teacher profile and returns authentication token.
    """
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
    """
    Public endpoint for teacher authentication.
    Validates credentials and returns authentication token.
    """
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
                
                # Verify grade/section if provided
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
    """
    Main attendance endpoint for listing and creating attendance records.
    Supports filtering by date, student name, and status.
    """
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

            # Apply filters
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
            
            # Extract and process data
            data = request.data.copy()
            qr_data = data.get('qr_data', '')
            
            # Parse QR data if present
            if qr_data:
                try:
                    qr_json = json.loads(qr_data)
                    data['student_lrn'] = qr_json.get('lrn', '')
                    if not data.get('student_name'):
                        data['student_name'] = qr_json.get('student', 'Unknown')
                except json.JSONDecodeError:
                    pass
            
            # Set date if not provided
            if not data.get('date'):
                data['date'] = datetime.now().date()
            
            # Determine session (AM/PM)
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
    """
    Detail view for updating and deleting specific attendance records.
    """
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
    """
    Endpoint for managing student absences.
    """
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
    """
    Detail view for updating and deleting specific absence records.
    """
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
    """
    Endpoint for managing student dropouts.
    """
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
    """
    Detail view for updating and deleting specific dropout records.
    """
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
    """
    Endpoint for tracking unauthorized persons on campus.
    """
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
    """
    Detail view for updating and deleting unauthorized person records.
    """
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
    """
    Public endpoint for viewing all attendance records.
    No authentication required.
    """
    queryset = Attendance.objects.all().order_by('-timestamp')
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []


# -----------------------------
# HELPER FUNCTIONS FOR SF2 GENERATION
# -----------------------------
def create_triangle_image(triangle_type, size=30):
    """
    Creates a triangular image for AM/PM markers (matching frontend design)
    triangle_type: 'AM' (top-left), 'PM' (bottom-right), 'BOTH' (full cell)
    Returns: PIL Image object
    """
    img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # Green color matching the frontend rgba(67, 160, 71, 0.85)
    green_color = (67, 160, 71, 217)
    
    if triangle_type == 'AM':
        # Top-left triangle
        triangle = [(0, 0), (0, size), (size, 0)]
        draw.polygon(triangle, fill=green_color)
    elif triangle_type == 'PM':
        # Bottom-right triangle
        triangle = [(size, size), (size, 0), (0, size)]
        draw.polygon(triangle, fill=green_color)
    elif triangle_type == 'BOTH':
        # Full square
        draw.rectangle([(0, 0), (size, size)], fill=green_color)
    
    return img


def create_absent_overlay(size=51):
    """
    Creates a red overlay for absent cells (matching frontend)
    Returns: PIL Image object
    """
    # Light red with opacity rgba(255, 127, 127, 0.92)
    img = Image.new('RGBA', (size, size), (255, 127, 127, 235))
    return img


def create_diagonal_line(size=51):
    """
    Creates a dashed diagonal line for present cells
    Returns: PIL Image object
    """
    img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # Black dashed diagonal
    draw.line([(3, size-3), (size-3, 3)], fill=(0, 0, 0, 255), width=2)
    
    return img


# -----------------------------
# GENERATE SF2 EXCEL - ENHANCED VERSION (FIXED)
# -----------------------------
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_sf2_excel(request):
    """
    Generate SF2 Excel report with enhanced attendance markers:
    - Green triangles for AM/PM attendance
    - Red shading for absences
    - Diagonal lines for present cells
    - Support for academic year (June to March)
    - Matches frontend visual design
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
        
        # Load workbook
        wb = load_workbook(template_file)
        
        # Month names for sheet navigation
        month_names = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", 
                      "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        
        # Fetch all attendance records for this teacher
        attendances = Attendance.objects.filter(
            teacher=teacher_profile
        ).order_by('date', 'timestamp')
        
        # Extract unique students from attendance
        students_set = set()
        for att in attendances:
            students_set.add((att.student_lrn or '', att.student_name))
        
        # Sort students alphabetically by name
        students = sorted(list(students_set), key=lambda x: x[1])
        
        # Organize attendance by student, month, and day
        # Structure: {student_key: {month: {day: {'am': bool, 'pm': bool}}}}
        attendance_data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {'am': False, 'pm': False})))
        
        for att in attendances:
            student_key = att.student_lrn or att.student_name
            month = month_names[att.date.month - 1]
            day = att.date.day
            
            # Determine if it's AM or PM
            if att.session:
                session = att.session.upper()
            else:
                # Fallback to timestamp hour
                session = 'AM' if att.timestamp.hour < 12 else 'PM'
            
            # Only mark if present (not absent)
            if att.status.lower() not in ['absent']:
                if session == 'AM':
                    attendance_data[student_key][month][day]['am'] = True
                else:
                    attendance_data[student_key][month][day]['pm'] = True
        
        # Current date for limiting future dates
        now = datetime.now()
        current_month = month_names[now.month - 1]
        current_day = now.date().day
        
        # Academic year boundaries
        ACADEMIC_START = 5  # June (0-indexed)
        ACADEMIC_END = 2    # March
        
        # Process each month
        for month in month_names:
            if month not in wb.sheetnames:
                continue
            
            ws = wb[month]
            month_index = month_names.index(month)
            
            # Check if month is within academic year up to current month
            now_month = now.month - 1
            is_academic_allowed = False
            
            if now_month >= ACADEMIC_START:
                # June to December
                is_academic_allowed = ACADEMIC_START <= month_index <= now_month
            elif now_month <= ACADEMIC_END:
                # January to March
                is_academic_allowed = (ACADEMIC_START <= month_index <= 11) or (0 <= month_index <= now_month)
            else:
                # April or May - academic year finished
                is_academic_allowed = (ACADEMIC_START <= month_index <= 11) or (0 <= month_index <= ACADEMIC_END)
            
            if not is_academic_allowed:
                continue
            
            # Find date header row (row 10 in template)
            date_header_row = 10
            
            # Find day columns (typically starting from column G = 7)
            day_columns = {}
            for col_idx in range(7, 38):  # Columns G to AL (7 to 38)
                try:
                    cell_value = ws.cell(row=date_header_row, column=col_idx).value
                    if cell_value:
                        # Try to extract day number
                        day_str = str(cell_value).strip()
                        # Handle various formats: "1", "1st", " 1 ", etc.
                        import re
                        match = re.match(r'(\d+)', day_str)
                        if match:
                            day_num = int(match.group(1))
                            if 1 <= day_num <= 31:
                                day_columns[day_num] = col_idx
                except:
                    pass
            
            # Student rows start at 13 for males, 64 for females (per template)
            male_start_row = 13
            female_start_row = 64
            
            # Process students (adjust based on gender if available in your model)
            for idx, (lrn, name) in enumerate(students):
                row_num = male_start_row + idx  # Adjust if you have gender separation
                
                # Add student name in column B
                name_cell = ws.cell(row=row_num, column=2)
                name_cell.value = name
                name_cell.alignment = Alignment(vertical='middle', horizontal='left')
                name_cell.font = Font(color='FF000000', size=10)
                
                student_key = lrn or name
                
                # Process each day
                for day in range(1, 32):
                    if day not in day_columns:
                        continue
                    
                    col_idx = day_columns[day]
                    
                    # Skip future dates in current month
                    if month == current_month and day > current_day:
                        continue
                    
                    cell = ws.cell(row=row_num, column=col_idx)
                    
                    # Get attendance for this day
                    has_am = attendance_data[student_key][month][day]['am']
                    has_pm = attendance_data[student_key][month][day]['pm']
                    
                    # Determine if present
                    is_present = has_am or has_pm
                    
                    if is_present:
                        # Clear any fills
                        cell.fill = PatternFill(fill_type=None)
                        cell.alignment = Alignment(vertical='middle', horizontal='center')
                        
                        # Add diagonal border (dashed line going up from bottom-left to top-right)
                        cell.border = Border(
                            top=Side(style='thin'),
                            left=Side(style='thin'),
                            bottom=Side(style='thin'),
                            right=Side(style='thin'),
                            diagonal=Side(style='dashed', color='FF000000'),
                            diagonalUp=True
                        )
                        
                        # Determine triangle type
                        if has_am and has_pm:
                            triangle_type = 'BOTH'
                        elif has_am:
                            triangle_type = 'AM'
                        else:
                            triangle_type = 'PM'
                        
                        # Create and add triangle image
                        triangle_img = create_triangle_image(triangle_type, size=30)
                        img_buffer = io.BytesIO()
                        triangle_img.save(img_buffer, format='PNG')
                        img_buffer.seek(0)
                        
                        excel_img = ExcelImage(img_buffer)
                        excel_img.width = 30
                        excel_img.height = 24
                        
                        # Position image in cell with offset for better alignment
                        cell_letter = get_column_letter(col_idx)
                        cell_address = f"{cell_letter}{row_num}"
                        
                        # Adjust anchor position based on triangle type
                        if triangle_type == 'AM':
                            # Top-left triangle - nudge slightly down and right
                            excel_img.anchor = cell_address
                        elif triangle_type == 'PM':
                            # Bottom-right triangle - position slightly offset
                            excel_img.anchor = cell_address
                        else:
                            # Full cell - center
                            excel_img.anchor = cell_address
                        
                        ws.add_image(excel_img)
                        
                    else:
                        # Mark as absent
                        cell.value = "X"
                        cell.alignment = Alignment(vertical='middle', horizontal='center')
                        
                        # Red fill (matching frontend color)
                        fill_color = 'FFFF7F7F'
                        cell.fill = PatternFill(
                            start_color=fill_color,
                            end_color=fill_color,
                            fill_type='solid'
                        )
                        
                        # Match font color to fill to hide X visually
                        cell.font = Font(color=fill_color)
                        
                        # Add border (no diagonal for absent)
                        cell.border = Border(
                            top=Side(style='thin'),
                            left=Side(style='thin'),
                            bottom=Side(style='thin'),
                            right=Side(style='thin')
                        )
                        
                        # Add red overlay image for better visibility
                        try:
                            absent_img = create_absent_overlay(size=51)
                            img_buffer = io.BytesIO()
                            absent_img.save(img_buffer, format='PNG')
                            img_buffer.seek(0)
                            
                            excel_img = ExcelImage(img_buffer)
                            excel_img.width = 51
                            excel_img.height = 43
                            
                            cell_letter = get_column_letter(col_idx)
                            cell_address = f"{cell_letter}{row_num}"
                            excel_img.anchor = cell_address
                            ws.add_image(excel_img)
                        except Exception as e:
                            # If image fails, the cell fill will still show
                            print(f"Warning: Could not add absent overlay image: {e}")
        
        # Save workbook to buffer
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        # Generate filename
        filename = f"SF2_Report_{teacher_profile.section.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        
        return FileResponse(
            buffer,
            as_attachment=True,
            filename=filename,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except TeacherProfile.DoesNotExist:
        return Response(
            {"error": "Teacher profile not found"}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return Response(
            {"error": f"Error generating SF2: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# -----------------------------
# DEMO ENDPOINT FOR TESTING
# -----------------------------
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def generate_half_triangle_demo(request):
    """
    Demo endpoint showing triangle markers (for testing)
    No authentication required - useful for frontend testing
    """
    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "Triangle Demo"
        
        # Headers
        ws['A1'] = "Type"
        ws['A1'].font = Font(bold=True)
        ws['B1'] = "Visual"
        ws['B1'].font = Font(bold=True)
        
        # Set column widths
        ws.column_dimensions['A'].width = 15
        ws.column_dimensions['B'].width = 15
        
        # Create examples
        types = [
            ('AM', 'Morning Session'),
            ('PM', 'Afternoon Session'),
            ('BOTH', 'Full Day'),
            ('ABSENT', 'Absent')
        ]
        
        for idx, (triangle_type, description) in enumerate(types, start=2):
            ws[f'A{idx}'] = description
            
            # Set row height for better visibility
            ws.row_dimensions[idx].height = 35
            
            if triangle_type == 'ABSENT':
                # Create absent cell
                cell = ws[f'B{idx}']
                cell.value = "X"
                cell.fill = PatternFill(
                    start_color='FFFF7F7F',
                    end_color='FFFF7F7F',
                    fill_type='solid'
                )
                cell.font = Font(color='FFFF7F7F')
                cell.alignment = Alignment(horizontal='center', vertical='center')
                
                # Add absent overlay
                try:
                    absent_img = create_absent_overlay(size=51)
                    img_buffer = io.BytesIO()
                    absent_img.save(img_buffer, format='PNG')
                    img_buffer.seek(0)
                    
                    excel_img = ExcelImage(img_buffer)
                    excel_img.width = 51
                    excel_img.height = 43
                    excel_img.anchor = f'B{idx}'
                    ws.add_image(excel_img)
                except:
                    pass
            else:
                # Create triangle
                img = create_triangle_image(triangle_type, size=30)
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='PNG')
                img_buffer.seek(0)
                
                excel_img = ExcelImage(img_buffer)
                excel_img.width = 30
                excel_img.height = 24
                excel_img.anchor = f'B{idx}'
                ws.add_image(excel_img)
                
                # Add diagonal border for present cells
                cell = ws[f'B{idx}']
                cell.border = Border(
                    top=Side(style='thin'),
                    left=Side(style='thin'),
                    bottom=Side(style='thin'),
                    right=Side(style='thin'),
                    diagonal=Side(style='dashed', color='FF000000'),
                    diagonalUp=True
                )
                cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # Add legend
        legend_row = len(types) + 3
        ws[f'A{legend_row}'] = "Legend:"
        ws[f'A{legend_row}'].font = Font(bold=True)
        
        ws[f'A{legend_row + 1}'] = "• AM = Top-left green triangle"
        ws[f'A{legend_row + 2}'] = "• PM = Bottom-right green triangle"
        ws[f'A{legend_row + 3}'] = "• BOTH = Full green square"
        ws[f'A{legend_row + 4}'] = "• ABSENT = Red background with X"
        
        # Save to buffer
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        return FileResponse(
            buffer,
            as_attachment=True,
            filename="sf2_triangle_demo.xlsx",
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return Response(
            {"error": f"Error generating demo: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# -----------------------------
# CUSTOM ERROR HANDLER
# -----------------------------
def custom_error_handler(exc, context):
    """
    Custom error handler for REST framework exceptions.
    Adds status_code to response data for better error handling.
    """
    from rest_framework.views import exception_handler
    response = exception_handler(exc, context)
    
    if response is not None:
        response.data['status_code'] = response.status_code
    else:
        response = Response(
            {"error": "Internal Server Error", "details": str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    return response
