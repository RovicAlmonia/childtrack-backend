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
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import io
import json
from datetime import datetime


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
# GENERATE SF2 EXCEL WITH HALF TRIANGLES
# -----------------------------
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_sf2_excel(request):
    """
    Generate SF2 (School Form 2) Excel report with half triangles for AM/PM attendance.
    Uses Unicode triangle symbols to indicate session attendance.
    """
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
        
        # Get month and year from request
        month = request.data.get('month', datetime.now().month)
        year = request.data.get('year', datetime.now().year)
        
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
        
        # Set up header
        ws['A1'] = "School Form 2 (SF2) Daily Attendance Report of Learners"
        ws.merge_cells('A1:AH1')
        ws['A1'].font = Font(bold=True, size=14)
        ws['A1'].alignment = Alignment(horizontal='center')
        
        # Column headers
        headers = ['No.', 'LRN', 'Name'] + [str(i) for i in range(1, 32)] + ['Total Present', 'Total Absent']
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=2, column=col_num)
            cell.value = header
            cell.font = Font(bold=True)
            cell.fill = PatternFill(
                start_color="4472C4", 
                end_color="4472C4", 
                fill_type="solid"
            )
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # Process attendance data by student
        student_data = {}
        for att in attendances:
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
            
            if day not in student_data[key]['attendance']:
                student_data[key]['attendance'][day] = {'am': None, 'pm': None}
            
            if session == 'AM':
                student_data[key]['attendance'][day]['am'] = status_val
            else:
                student_data[key]['attendance'][day]['pm'] = status_val
        
        # Fill in student rows
        row_num = 3
        for idx, ((lrn, name), data) in enumerate(
            sorted(student_data.items(), key=lambda x: x[1]['name']), 1
        ):
            ws.cell(row=row_num, column=1).value = idx
            ws.cell(row=row_num, column=2).value = lrn
            ws.cell(row=row_num, column=3).value = name
            
            total_present = 0
            total_absent = 0
            
            # Fill attendance for each day of the month
            for day in range(1, 32):
                col = day + 3
                cell = ws.cell(row=row_num, column=col)
                
                if day in data['attendance']:
                    am_status = data['attendance'][day]['am']
                    pm_status = data['attendance'][day]['pm']
                    
                    # Handle absent status
                    if am_status == 'absent' or pm_status == 'absent':
                        cell.value = 'A'
                        cell.fill = PatternFill(
                            start_color="FF0000", 
                            end_color="FF0000", 
                            fill_type="solid"
                        )
                        cell.font = Font(color="FFFFFF", bold=True)
                        total_absent += 1
                    # Handle present status with triangle symbols
                    elif am_status or pm_status:
                        if am_status and pm_status:
                            cell.value = "◆"  # Both sessions - full diamond
                        elif am_status:
                            cell.value = "▼"  # AM only - down triangle
                        else:
                            cell.value = "▲"  # PM only - up triangle
                        
                        cell.font = Font(
                            name="Segoe UI Symbol", 
                            size=12, 
                            color="00B050", 
                            bold=True
                        )
                        cell.fill = PatternFill(
                            start_color="E2EFDA", 
                            end_color="E2EFDA", 
                            fill_type="solid"
                        )
                        total_present += 1
                
                # Apply borders to all cells
                cell.alignment = Alignment(horizontal='center', vertical='center')
                cell.border = Border(
                    left=Side(style='thin'),
                    right=Side(style='thin'),
                    top=Side(style='thin'),
                    bottom=Side(style='thin')
                )
            
            # Add totals
            ws.cell(row=row_num, column=35).value = total_present
            ws.cell(row=row_num, column=36).value = total_absent
            
            row_num += 1
        
        # Adjust column widths
        ws.column_dimensions['A'].width = 5
        ws.column_dimensions['B'].width = 15
        ws.column_dimensions['C'].width = 30
        for col in range(4, 37):
            ws.column_dimensions[get_column_letter(col)].width = 4
        
        # Save to buffer
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        filename = f"SF2_{teacher_profile.section}_{month}_{year}.xlsx"
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
def generate_half_triangle_excel(request):
    """
    Demo endpoint that generates an Excel file showing half-triangle symbols.
    Uses Unicode triangle characters for visual representation.
    """
    # Create workbook and worksheet
    wb = Workbook()
    ws = wb.active
    ws.title = "Half Triangle Demo"

    # Set column width
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 30

    # Define colors
    red_fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
    green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")
    blue_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")

    # Header
    ws["A1"].value = "Symbol"
    ws["A1"].fill = blue_fill
    ws["A1"].font = Font(color="FFFFFF", bold=True)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    
    ws["B1"].value = "Description"
    ws["B1"].fill = blue_fill
    ws["B1"].font = Font(color="FFFFFF", bold=True)
    ws["B1"].alignment = Alignment(horizontal="center", vertical="center")

    # AM triangle
    ws["A2"].value = "▼"
    ws["A2"].fill = green_fill
    ws["A2"].alignment = Alignment(horizontal="center", vertical="center")
    ws["A2"].font = Font(name="Segoe UI Symbol", size=14, color="FFFFFF", bold=True)
    ws["B2"].value = "AM Session (Down Triangle)"
    ws["B2"].alignment = Alignment(horizontal="left", vertical="center")

    # PM triangle
    ws["A3"].value = "▲"
    ws["A3"].fill = green_fill
    ws["A3"].alignment = Alignment(horizontal="center", vertical="center")
    ws["A3"].font = Font(name="Segoe UI Symbol", size=14, color="FFFFFF", bold=True)
    ws["B3"].value = "PM Session (Up Triangle)"
    ws["B3"].alignment = Alignment(horizontal="left", vertical="center")

    # Both sessions
    ws["A4"].value = "◆"
    ws["A4"].fill = green_fill
    ws["A4"].alignment = Alignment(horizontal="center", vertical="center")
    ws["A4"].font = Font(name="Segoe UI Symbol", size=14, color="FFFFFF", bold=True)
    ws["B4"].value = "Both Sessions (Diamond)"
    ws["B4"].alignment = Alignment(horizontal="left", vertical="center")

    # Absent
    ws["A5"].value = "A"
    ws["A5"].fill = red_fill
    ws["A5"].alignment = Alignment(horizontal="center", vertical="center")
    ws["A5"].font = Font(color="FFFFFF", bold=True)
    ws["B5"].value = "Absent"
    ws["B5"].alignment = Alignment(horizontal="left", vertical="center")

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


from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image as ExcelImage
import io
import json
from datetime import datetime
from PIL import Image, ImageDraw
import base64


# Keep all your existing view classes (RegisterView, LoginView, AttendanceView, etc.)
# I'm only showing the modified SF2 generation functions


def create_half_triangle_image(session_type, is_absent=False):
    """
    Creates a half-filled triangle image for AM/PM sessions
    session_type: 'AM', 'PM', or 'BOTH'
    is_absent: if True, returns red background
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
            font = ImageFont.truetype("arial.ttf", 60)
        except:
            font = ImageFont.load_default()
        text = "A"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        position = ((size - text_width) // 2, (size - text_height) // 2)
        draw.text(position, text, fill='white', font=font)
    elif session_type == 'AM':
        # Bottom-left green triangle for AM
        triangle = [(0, size), (size, size), (0, 0)]
        draw.polygon(triangle, fill='#00B050')
    elif session_type == 'PM':
        # Top-right green triangle for PM
        triangle = [(0, 0), (size, 0), (size, size)]
        draw.polygon(triangle, fill='#00B050')
    elif session_type == 'BOTH':
        # Full green diamond/square for both sessions
        draw.rectangle([(0, 0), (size, size)], fill='#00B050')
    
    return img


def add_image_to_cell(ws, img, cell):
    """
    Adds a PIL Image to an Excel cell
    """
    # Save image to BytesIO buffer
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    
    # Create Excel image
    excel_img = ExcelImage(img_buffer)
    
    # Scale image to fit cell (approximately)
    excel_img.width = 30
    excel_img.height = 30
    
    # Add image to worksheet at cell location
    ws.add_image(excel_img, cell)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_sf2_excel(request):
    """
    Generate SF2 (School Form 2) Excel report with half-triangle images for AM/PM attendance.
    Now creates actual triangle images instead of Unicode symbols for better visual representation.
    """
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
        
        # Get month and year from request
        month = request.data.get('month', datetime.now().month)
        year = request.data.get('year', datetime.now().year)
        
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
        
        # Set up header
        ws['A1'] = "School Form 2 (SF2) Daily Attendance Report of Learners"
        ws.merge_cells('A1:AH1')
        ws['A1'].font = Font(bold=True, size=14)
        ws['A1'].alignment = Alignment(horizontal='center')
        
        # Add school information
        ws['A2'] = f"School: {teacher_profile.section}"
        ws['A3'] = f"Month: {datetime(year, month, 1).strftime('%B %Y')}"
        ws['A4'] = f"Teacher: {teacher_profile.user.first_name or teacher_profile.user.username}"
        
        # Column headers (starting at row 6)
        header_row = 6
        headers = ['No.', 'LRN', 'Name'] + [str(i) for i in range(1, 32)] + ['Total Present', 'Total Absent', 'Total Tardy']
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=header_row, column=col_num)
            cell.value = header
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(
                start_color="4472C4", 
                end_color="4472C4", 
                fill_type="solid"
            )
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
        
        # Process attendance data by student
        student_data = {}
        for att in attendances:
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
            
            if day not in student_data[key]['attendance']:
                student_data[key]['attendance'][day] = {'am': None, 'pm': None}
            
            if session == 'AM':
                student_data[key]['attendance'][day]['am'] = status_val
            else:
                student_data[key]['attendance'][day]['pm'] = status_val
        
        # Set row height for better image display
        for row in range(header_row + 1, header_row + len(student_data) + 1):
            ws.row_dimensions[row].height = 30
        
        # Set column widths
        ws.column_dimensions['A'].width = 5
        ws.column_dimensions['B'].width = 15
        ws.column_dimensions['C'].width = 30
        for col in range(4, 37):
            ws.column_dimensions[get_column_letter(col)].width = 5
        ws.column_dimensions[get_column_letter(35)].width = 12  # Total Present
        ws.column_dimensions[get_column_letter(36)].width = 12  # Total Absent
        ws.column_dimensions[get_column_letter(37)].width = 12  # Total Tardy
        
        # Fill in student rows
        row_num = header_row + 1
        for idx, ((lrn, name), data) in enumerate(
            sorted(student_data.items(), key=lambda x: x[1]['name']), 1
        ):
            ws.cell(row=row_num, column=1).value = idx
            ws.cell(row=row_num, column=2).value = lrn
            ws.cell(row=row_num, column=3).value = name
            
            total_present = 0
            total_absent = 0
            total_tardy = 0
            
            # Fill attendance for each day of the month
            for day in range(1, 32):
                col = day + 3
                cell = ws.cell(row=row_num, column=col)
                cell_ref = f"{get_column_letter(col)}{row_num}"
                
                # Apply borders
                cell.border = Border(
                    left=Side(style='thin'),
                    right=Side(style='thin'),
                    top=Side(style='thin'),
                    bottom=Side(style='thin')
                )
                cell.alignment = Alignment(horizontal='center', vertical='center')
                
                if day in data['attendance']:
                    am_status = data['attendance'][day]['am']
                    pm_status = data['attendance'][day]['pm']
                    
                    # Determine if absent
                    is_absent = am_status == 'absent' or pm_status == 'absent'
                    
                    # Determine session type
                    if is_absent:
                        session_type = 'ABSENT'
                        total_absent += 1
                    elif am_status and pm_status:
                        session_type = 'BOTH'
                        total_present += 1
                    elif am_status:
                        session_type = 'AM'
                        total_present += 0.5
                    elif pm_status:
                        session_type = 'PM'
                        total_present += 0.5
                    else:
                        continue
                    
                    # Check for tardiness (late)
                    if am_status == 'late' or pm_status == 'late':
                        total_tardy += 1
                    
                    # Create and add triangle image
                    if session_type == 'ABSENT':
                        img = create_half_triangle_image('AM', is_absent=True)
                    else:
                        img = create_half_triangle_image(session_type, is_absent=False)
                    
                    add_image_to_cell(ws, img, cell_ref)
            
            # Add totals
            ws.cell(row=row_num, column=35).value = int(total_present)
            ws.cell(row=row_num, column=36).value = total_absent
            ws.cell(row=row_num, column=37).value = total_tardy
            
            # Style total cells
            for col in [35, 36, 37]:
                cell = ws.cell(row=row_num, column=col)
                cell.alignment = Alignment(horizontal='center', vertical='center')
                cell.border = Border(
                    left=Side(style='thin'),
                    right=Side(style='thin'),
                    top=Side(style='thin'),
                    bottom=Side(style='thin')
                )
            
            row_num += 1
        
        # Add legend at the bottom
        legend_row = row_num + 2
        ws.cell(row=legend_row, column=1).value = "Legend:"
        ws.cell(row=legend_row, column=1).font = Font(bold=True)
        
        ws.cell(row=legend_row + 1, column=1).value = "▼ (Bottom-left green) = AM Session"
        ws.cell(row=legend_row + 2, column=1).value = "▲ (Top-right green) = PM Session"
        ws.cell(row=legend_row + 3, column=1).value = "■ (Full green) = Both Sessions"
        ws.cell(row=legend_row + 4, column=1).value = "A (Red background) = Absent"
        
        # Save to buffer
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        filename = f"SF2_{teacher_profile.section}_{month}_{year}.xlsx"
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


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def generate_half_triangle_demo(request):
    """
    Demo endpoint that generates an Excel file showing half-triangle images.
    Demonstrates the visual appearance of AM/PM/Both/Absent markers.
    """
    # Create workbook and worksheet
    wb = Workbook()
    ws = wb.active
    ws.title = "Half Triangle Demo"

    # Set column widths and row heights
    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 30
    for row in range(2, 7):
        ws.row_dimensions[row].height = 35

    # Define colors
    blue_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")

    # Header
    ws["A1"].value = "Example"
    ws["A1"].fill = blue_fill
    ws["A1"].font = Font(color="FFFFFF", bold=True)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    
    ws["B1"].value = "Description"
    ws["B1"].fill = blue_fill
    ws["B1"].font = Font(color="FFFFFF", bold=True)
    ws["B1"].alignment = Alignment(horizontal="center", vertical="center")

    # AM triangle
    am_img = create_half_triangle_image('AM')
    add_image_to_cell(ws, am_img, 'A2')
    ws["B2"].value = "AM Session (Bottom-left green triangle)"
    ws["B2"].alignment = Alignment(horizontal="left", vertical="center")

    # PM triangle
    pm_img = create_half_triangle_image('PM')
    add_image_to_cell(ws, pm_img, 'A3')
    ws["B3"].value = "PM Session (Top-right green triangle)"
    ws["B3"].alignment = Alignment(horizontal="left", vertical="center")

    # Both sessions
    both_img = create_half_triangle_image('BOTH')
    add_image_to_cell(ws, both_img, 'A4')
    ws["B4"].value = "Both Sessions (Full green square)"
    ws["B4"].alignment = Alignment(horizontal="left", vertical="center")

    # Absent
    absent_img = create_half_triangle_image('AM', is_absent=True)
    add_image_to_cell(ws, absent_img, 'A5')
    ws["B5"].value = "Absent (Red background with 'A')"
    ws["B5"].alignment = Alignment(horizontal="left", vertical="center")

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
