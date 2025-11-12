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
# GENERATE SF2 EXCEL - POPULATE EXISTING TEMPLATE
# -----------------------------
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_sf2_excel(request):
    """
    Generate SF2 (School Form 2) Excel report by populating an existing template.
    Inserts student names and attendance marks without modifying the template structure.
    
    Request body (JSON):
        - month (optional): month number (1-12), defaults to current month
        - year (optional): year number, defaults to current year
        - template_file (optional): uploaded SF2 template file
    
    Returns:
        Excel file with attendance data populated in the template
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
        
        # Check if template file is provided in request.FILES
        template_file = request.FILES.get('template_file')
        
        if not template_file:
            return Response(
                {"error": "Please upload an SF2 template file"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Load the template workbook
        wb = load_workbook(template_file)
        
        # Get the active worksheet (assuming SF2 is in the first/active sheet)
        ws = wb.active
        
        # Process attendance data by student
        student_data = {}
        
        for att in attendances:
            # Use student name as unique key (combine with LRN if needed)
            key = att.student_name
            
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
        
        # Sort students alphabetically
        sorted_students = sorted(student_data.items(), key=lambda x: x[1]['name'])
        
        # Starting row for student data (adjust based on your template - typically row 4 or 5)
        start_row = 4  # Change this to match your template's first student row
        
        # Column indices (adjust based on your template structure)
        # Assuming: A=No, B=LRN, C=Name, D-AH=Days 1-31, etc.
        lrn_col = 2      # Column B
        name_col = 3     # Column C
        day_start_col = 4  # Column D (day 1)
        
        # Populate student data
        for idx, (student_name, data) in enumerate(sorted_students):
            row_num = start_row + idx
            
            # Ensure row exists
            if row_num > ws.max_row:
                ws.append([])
            
            # Insert student number (optional, if template has this)
            ws.cell(row=row_num, column=1).value = idx + 1
            
            # Insert LRN
            if data['lrn']:
                ws.cell(row=row_num, column=lrn_col).value = data['lrn']
            
            # Insert student name
            ws.cell(row=row_num, column=name_col).value = data['name']
            
            # Initialize counters for totals
            total_present = 0
            total_absent = 0
            
            # Fill attendance for each day of the month
            for day in range(1, 32):
                col = day_start_col + day - 1
                cell = ws.cell(row=row_num, column=col)
                
                # Check if there's attendance data for this day
                if day in data['attendance']:
                    am_status = data['attendance'][day]['am']
                    pm_status = data['attendance'][day]['pm']
                    
                    # Determine attendance marking
                    is_absent_am = am_status == 'absent'
                    is_absent_pm = pm_status == 'absent'
                    
                    if is_absent_am and is_absent_pm:
                        # Full day absent - Red fill with "x"
                        cell.value = "x"
                        cell.fill = PatternFill(
                            start_color="FFB6B6",  # Light red
                            end_color="FFB6B6",
                            fill_type="solid"
                        )
                        total_absent += 1
                    elif is_absent_am or is_absent_pm:
                        # Half day absent - mark accordingly
                        if is_absent_am:
                            cell.fill = PatternFill(
                                start_color="FFB6B6",
                                end_color="FFB6B6",
                                fill_type="solid"
                            )
                        else:
                            cell.fill = PatternFill(
                                start_color="90EE90",  # Light green
                                end_color="90EE90",
                                fill_type="solid"
                            )
                        total_absent += 0.5
                        total_present += 0.5
                    elif am_status or pm_status:
                        # Present (full or half day)
                        if am_status and pm_status:
                            # Full day present - full green fill
                            cell.fill = PatternFill(
                                start_color="90EE90",
                                end_color="90EE90",
                                fill_type="solid"
                            )
                            total_present += 1
                        elif am_status:
                            # AM only - half green (bottom)
                            cell.fill = PatternFill(
                                start_color="90EE90",
                                end_color="90EE90",
                                fill_type="solid"
                            )
                            total_present += 0.5
                        elif pm_status:
                            # PM only - half green (top)
                            cell.fill = PatternFill(
                                start_color="90EE90",
                                end_color="90EE90",
                                fill_type="solid"
                            )
                            total_present += 0.5
                    
                    # Add border to marked cells
                    cell.border = Border(
                        left=Side(style='thin', color='000000'),
                        right=Side(style='thin', color='000000'),
                        top=Side(style='thin', color='000000'),
                        bottom=Side(style='thin', color='000000')
                    )
                    
                    # Center align
                    cell.alignment = Alignment(horizontal='center', vertical='center')
            
            # Add total absent and present counts (adjust column indices based on your template)
            # Assuming columns after day 31 are for totals
            absent_col = day_start_col + 31  # Adjust as needed
            present_col = absent_col + 1     # Adjust as needed
            
            ws.cell(row=row_num, column=absent_col).value = int(total_absent)
            ws.cell(row=row_num, column=present_col).value = int(total_present)
        
        # Save to buffer
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        # Generate filename
        month_name = datetime(year, month, 1).strftime('%B')
        filename = f"SF2_{teacher_profile.section.replace(' ', '_')}_{month_name}_{year}.xlsx"
        
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
