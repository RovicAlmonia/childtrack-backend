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
from PIL import Image, ImageDraw
import base64


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
def create_half_triangle_image(session_type, is_absent=False):
    """
    Creates a half-filled triangle image for AM/PM sessions
    session_type: 'AM', 'PM', or 'BOTH'
    is_absent: if True, returns red background with 'A'
    Returns: PIL Image object
    """
    # Create a square image
    size = 100
    img = Image.new('RGB', (size, size), 'white')
    draw = ImageDraw.Draw(img)
    
    if is_absent:
        # Full red background for absent
        draw.rectangle([(0, 0), (size, size)], fill='#FF0000')
        
        # White 'A' text
        from PIL import ImageFont
        try:
            # Try to use a TrueType font if available
            font = ImageFont.truetype("arial.ttf", 60)
        except:
            try:
                # Try alternative font paths
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
            except:
                # Fall back to default font
                font = ImageFont.load_default()
        
        text = "A"
        # Get text bounding box
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Center the text
        position = ((size - text_width) // 2, (size - text_height) // 2)
        draw.text(position, text, fill='white', font=font)
        
    elif session_type == 'AM':
        # Bottom-left green triangle for AM (Morning)
        # Points: bottom-left, bottom-right, top-left
        triangle = [(0, size), (size, size), (0, 0)]
        draw.polygon(triangle, fill='#00B050')
        
    elif session_type == 'PM':
        # Top-right green triangle for PM (Afternoon)
        # Points: top-left, top-right, bottom-right
        triangle = [(0, 0), (size, 0), (size, size)]
        draw.polygon(triangle, fill='#00B050')
        
    elif session_type == 'BOTH':
        # Full green square for both sessions
        draw.rectangle([(0, 0), (size, size)], fill='#00B050')
    
    return img


def add_image_to_cell(ws, img, cell):
    """
    Adds a PIL Image to an Excel cell
    
    Args:
        ws: worksheet object
        img: PIL Image object
        cell: cell reference string (e.g., 'A1')
    """
    # Save image to BytesIO buffer
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    
    # Create Excel image object
    excel_img = ExcelImage(img_buffer)
    
    # Scale image to fit cell (approximately 30x30 pixels)
    excel_img.width = 30
    excel_img.height = 30
    
    # Add image to worksheet at cell location
    ws.add_image(excel_img, cell)


# -----------------------------
# GENERATE SF2 EXCEL WITH HALF TRIANGLES
# -----------------------------
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_sf2_excel(request):
    """
    Generate SF2 (School Form 2) Excel report with half-triangle images for AM/PM attendance.
    
    Request body (JSON):
        - month (optional): month number (1-12), defaults to current month
        - year (optional): year number, defaults to current year
    
    Returns:
        Excel file with attendance data visualized using half-triangle images
    """
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
        
        # Get month and year from request
        month = request.data.get('month', datetime.now().month)
        year = request.data.get('year', datetime.now().year)
        
        # Convert to integers if they're strings
        try:
            month = int(month)
            year = int(year)
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid month or year format"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate month and year
        if not (1 <= month <= 12):
            return Response(
                {"error": "Month must be between 1 and 12"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not (2000 <= year <= 2100):
            return Response(
                {"error": "Year must be between 2000 and 2100"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Fetch attendance records for the specified period
        attendances = Attendance.objects.filter(
            teacher=teacher_profile,
            date__month=month,
            date__year=year
        ).order_by('student_name', 'date')
        
        # Create workbook and worksheet
        wb = Workbook()
        ws = wb.active
        ws.title = f"SF2_{month}_{year}"
        
        # Set up main header
        ws['A1'] = "School Form 2 (SF2) Daily Attendance Report of Learners"
        ws.merge_cells('A1:AH1')
        ws['A1'].font = Font(bold=True, size=14)
        ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
        
        # Add school information
        ws['A2'] = f"School/Section: {teacher_profile.section}"
        ws['A3'] = f"Month: {datetime(year, month, 1).strftime('%B %Y')}"
        ws['A4'] = f"Teacher: {teacher_profile.user.first_name or teacher_profile.user.username}"
        
        # Style info rows
        for row in range(2, 5):
            ws[f'A{row}'].font = Font(bold=True, size=11)
            ws[f'A{row}'].alignment = Alignment(horizontal='left', vertical='center')
        
        # Column headers (starting at row 6)
        header_row = 6
        headers = ['No.', 'LRN', 'Name'] + [str(i) for i in range(1, 32)] + ['Total Present', 'Total Absent', 'Total Tardy']
        
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=header_row, column=col_num)
            cell.value = header
            cell.font = Font(bold=True, color="FFFFFF", size=10)
            cell.fill = PatternFill(
                start_color="4472C4", 
                end_color="4472C4", 
                fill_type="solid"
            )
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = Border(
                left=Side(style='thin', color='000000'),
                right=Side(style='thin', color='000000'),
                top=Side(style='thin', color='000000'),
                bottom=Side(style='thin', color='000000')
            )
        
        # Process attendance data by student
        student_data = {}
        
        for att in attendances:
            # Use LRN and name as unique key
            key = (att.student_lrn or "", att.student_name)
            
            if key not in student_data:
                student_data[key] = {
                    'lrn': att.student_lrn or "",
                    'name': att.student_name,
                    'attendance': {}
                }
            
            day = att.date.day
            session = att.session or ('AM' if att.timestamp.hour < 12 else 'PM')
            status_val = att.status.lower()
            
            # Initialize day if not exists
            if day not in student_data[key]['attendance']:
                student_data[key]['attendance'][day] = {'am': None, 'pm': None}
            
            # Store attendance by session
            if session == 'AM':
                student_data[key]['attendance'][day]['am'] = status_val
            else:
                student_data[key]['attendance'][day]['pm'] = status_val
        
        # Set row height for better image display
        for row in range(header_row + 1, header_row + len(student_data) + 1):
            ws.row_dimensions[row].height = 30
        
        # Set column widths
        ws.column_dimensions['A'].width = 5   # No.
        ws.column_dimensions['B'].width = 15  # LRN
        ws.column_dimensions['C'].width = 30  # Name
        
        # Day columns (1-31)
        for col in range(4, 35):
            ws.column_dimensions[get_column_letter(col)].width = 5
        
        # Total columns
        ws.column_dimensions[get_column_letter(35)].width = 12  # Total Present
        ws.column_dimensions[get_column_letter(36)].width = 12  # Total Absent
        ws.column_dimensions[get_column_letter(37)].width = 12  # Total Tardy
        
        # Fill in student rows
        row_num = header_row + 1
        
        for idx, ((lrn, name), data) in enumerate(
            sorted(student_data.items(), key=lambda x: x[1]['name']), 1
        ):
            # Student info columns
            ws.cell(row=row_num, column=1).value = idx
            ws.cell(row=row_num, column=2).value = lrn
            ws.cell(row=row_num, column=3).value = name
            
            # Style student info cells
            for col in [1, 2, 3]:
                cell = ws.cell(row=row_num, column=col)
                cell.alignment = Alignment(horizontal='left' if col == 3 else 'center', vertical='center')
                cell.border = Border(
                    left=Side(style='thin'),
                    right=Side(style='thin'),
                    top=Side(style='thin'),
                    bottom=Side(style='thin')
                )
            
            # Initialize counters
            total_present = 0
            total_absent = 0
            total_tardy = 0
            
            # Fill attendance for each day of the month
            for day in range(1, 32):
                col = day + 3
                cell = ws.cell(row=row_num, column=col)
                cell_ref = f"{get_column_letter(col)}{row_num}"
                
                # Apply borders to all cells
                cell.border = Border(
                    left=Side(style='thin', color='CCCCCC'),
                    right=Side(style='thin', color='CCCCCC'),
                    top=Side(style='thin', color='CCCCCC'),
                    bottom=Side(style='thin', color='CCCCCC')
                )
                cell.alignment = Alignment(horizontal='center', vertical='center')
                
                # Check if there's attendance data for this day
                if day in data['attendance']:
                    am_status = data['attendance'][day]['am']
                    pm_status = data['attendance'][day]['pm']
                    
                    # Determine if student is absent
                    is_absent = am_status == 'absent' or pm_status == 'absent'
                    
                    # Determine session type for image
                    if is_absent:
                        session_type = 'ABSENT'
                        total_absent += 1
                    elif am_status and pm_status:
                        # Both AM and PM present
                        session_type = 'BOTH'
                        total_present += 1
                    elif am_status:
                        # Only AM present
                        session_type = 'AM'
                        total_present += 0.5
                    elif pm_status:
                        # Only PM present
                        session_type = 'PM'
                        total_present += 0.5
                    else:
                        # No valid attendance
                        continue
                    
                    # Check for tardiness (late status)
                    if am_status == 'late' or pm_status == 'late':
                        total_tardy += 1
                    
                    # Create and add triangle image to cell
                    if session_type == 'ABSENT':
                        img = create_half_triangle_image('AM', is_absent=True)
                    else:
                        img = create_half_triangle_image(session_type, is_absent=False)
                    
                    add_image_to_cell(ws, img, cell_ref)
            
            # Add totals to the row
            total_present_cell = ws.cell(row=row_num, column=35)
            total_present_cell.value = int(total_present)
            total_present_cell.alignment = Alignment(horizontal='center', vertical='center')
            total_present_cell.border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            total_present_cell.font = Font(bold=True, color="00B050")
            
            total_absent_cell = ws.cell(row=row_num, column=36)
            total_absent_cell.value = total_absent
            total_absent_cell.alignment = Alignment(horizontal='center', vertical='center')
            total_absent_cell.border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            total_absent_cell.font = Font(bold=True, color="FF0000")
            
            total_tardy_cell = ws.cell(row=row_num, column=37)
            total_tardy_cell.value = total_tardy
            total_tardy_cell.alignment = Alignment(horizontal='center', vertical='center')
            total_tardy_cell.border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            total_tardy_cell.font = Font(bold=True, color="FFC107")
            
            row_num += 1
        
        # Add legend at the bottom
        legend_row = row_num + 2
        
        ws.cell(row=legend_row, column=1).value = "LEGEND:"
        ws.cell(row=legend_row, column=1).font = Font(bold=True, size=12)
        
        ws.cell(row=legend_row + 1, column=1).value = "▼ Bottom-left green triangle = AM Session (Morning)"
        ws.cell(row=legend_row + 2, column=1).value = "▲ Top-right green triangle = PM Session (Afternoon)"
        ws.cell(row=legend_row + 3, column=1).value = "■ Full green square = Both AM and PM Sessions"
        ws.cell(row=legend_row + 4, column=1).value = "A Red background with 'A' = Absent"
        
        for i in range(1, 5):
            ws.cell(row=legend_row + i, column=1).font = Font(size=10)
        
        # Save to buffer
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        # Generate filename
        filename = f"SF2_{teacher_profile.section.replace(' ', '_')}_{month:02d}_{year}.xlsx"
        
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
# GENERATE HALF TRIANGLE DEMO EXCEL
# -----------------------------
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def generate_half_triangle_demo(request):
    """
    Demo endpoint that generates an Excel file showing half-triangle images.
    Demonstrates the visual appearance of AM/PM/Both/Absent markers.
    No authentication required - public endpoint for testing.
    """
    try:
        # Create workbook and worksheet
        wb = Workbook()
        ws = wb.active
        ws.title = "Half Triangle Demo"

        # Set column widths and row heights
        ws.column_dimensions['A'].width = 8
        ws.column_dimensions['B'].width = 35
        
        for row in range(2, 7):
            ws.row_dimensions[row].height = 35

        # Define colors
        blue_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")

        # Header row
        ws["A1"].value = "Example"
        ws["A1"].fill = blue_fill
        ws["A1"].font = Font(color="FFFFFF", bold=True, size=12)
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
        
        ws["B1"].value = "Description"
        ws["B1"].fill = blue_fill
        ws["B1"].font = Font(color="FFFFFF", bold=True, size=12)
        ws["B1"].alignment = Alignment(horizontal="center", vertical="center")

        # AM triangle example
        am_img = create_half_triangle_image('AM')
        add_image_to_cell(ws, am_img, 'A2')
        ws["B2"].value = "AM Session (Morning) - Bottom-left green triangle"
        ws["B2"].alignment = Alignment(horizontal="left", vertical="center")
        ws["B2"].font = Font(size=11)

        # PM triangle example
        pm_img = create_half_triangle_image('PM')
        add_image_to_cell(ws, pm_img, 'A3')
        ws["B3"].value = "PM Session (Afternoon) - Top-right green triangle"
        ws["B3"].alignment = Alignment(horizontal="left", vertical="center")
        ws["B3"].font = Font(size=11)

        # Both sessions example
        both_img = create_half_triangle_image('BOTH')
        add_image_to_cell(ws, both_img, 'A4')
        ws["B4"].value = "Both Sessions - Full green square"
        ws["B4"].alignment = Alignment(horizontal="left", vertical="center")
        ws["B4"].font = Font(size=11)

        # Absent example
        absent_img = create_half_triangle_image('AM', is_absent=True)
        add_image_to_cell(ws, absent_img, 'A5')
        ws["B5"].value = "Absent - Red background with 'A'"
        ws["B5"].alignment = Alignment(horizontal="left", vertical="center")
        ws["B5"].font = Font(size=11)

        # Add borders to all cells
        for row in range(1, 6):
            for col in ['A', 'B']:
                ws[f"{col}{row}"].border = Border(
                    left=Side(style='thin'),
                    right=Side(style='thin'),
                    top=Side(style='thin'),
                    bottom=Side(style='thin')
                )

        # Save to BytesIO buffer
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        # Return Excel file
        return FileResponse(
            buffer, 
            as_attachment=True, 
            filename="half_triangle_demo.xlsx",
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
