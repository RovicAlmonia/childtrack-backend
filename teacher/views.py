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
from datetime import datetime

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
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return Response({"error": "User not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)

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
            return Response({"error": f"Error fetching attendance: {str(e)}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            
            # Extract data from request
            data = request.data.copy()
            qr_data = data.get('qr_data', '')
            
            # Parse QR data if it's JSON
            if qr_data:
                try:
                    import json
                    qr_json = json.loads(qr_data)
                    data['student_lrn'] = qr_json.get('lrn', '')
                    if not data.get('student_name'):
                        data['student_name'] = qr_json.get('student', 'Unknown')
                except:
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
# GENERATE SF2 WITH HALF TRIANGLES
# -----------------------------
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_sf2_excel(request):
    """
    Generate SF2 Excel with half triangles for AM/PM attendance
    """
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
        
        # Get attendance records
        month = request.data.get('month', datetime.now().month)
        year = request.data.get('year', datetime.now().year)
        
        attendances = Attendance.objects.filter(
            teacher=teacher_profile,
            date__month=month,
            date__year=year
        ).order_by('student_name', 'date')
        
        # Create workbook
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
            cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # Process attendance data
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
            status = att.status.lower()
            
            if day not in student_data[key]['attendance']:
                student_data[key]['attendance'][day] = {'am': None, 'pm': None}
            
            if session == 'AM':
                student_data[key]['attendance'][day]['am'] = status
            else:
                student_data[key]['attendance'][day]['pm'] = status
        
        # Fill in student rows
        row_num = 3
        for idx, ((lrn, name), data) in enumerate(sorted(student_data.items(), key=lambda x: x[1]['name']), 1):
            ws.cell(row=row_num, column=1).value = idx
            ws.cell(row=row_num, column=2).value = lrn
            ws.cell(row=row_num, column=3).value = name
            
            total_present = 0
            total_absent = 0
            
            # Fill attendance for each day
            for day in range(1, 32):
                col = day + 3
                cell = ws.cell(row=row_num, column=col)
                
                if day in data['attendance']:
                    am_status = data['attendance'][day]['am']
                    pm_status = data['attendance'][day]['pm']
                    
                    # Handle absent
                    if am_status == 'absent' or pm_status == 'absent':
                        cell.value = 'A'
                        cell.fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
                        cell.font = Font(color="FFFFFF", bold=True)
                        total_absent += 1
                    # Handle present - use triangle symbols
                    elif am_status or pm_status:
                        # AM = ▼ (down triangle), PM = ▲ (up triangle)
                        if am_status and pm_status:
                            cell.value = "◆"  # Both sessions - full diamond
                        elif am_status:
                            cell.value = "▼"  # AM only - down triangle
                        else:
                            cell.value = "▲"  # PM only - up triangle
                        
                        cell.font = Font(name="Segoe UI Symbol", size=12, color="00B050", bold=True)
                        cell.fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
                        total_present += 1
                
                # Style all cells
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
        return Response({"error": "Teacher profile not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return Response({"error": f"Error generating SF2: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# -----------------------------
# CUSTOM ERROR HANDLER
# -----------------------------
def custom_error_handler(exc, context):
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
from openpyxl.drawing.spreadsheet_drawing import SpreadsheetDrawing
from openpyxl.drawing.shapes import Polygon
from openpyxl.drawing.fill import SolidFill
from openpyxl.drawing.xdr import XDRPoint2D, XDRPositiveSize2D, XDRShape
import io
from datetime import datetime


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
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return Response({"error": "User not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)

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
            return Response({"error": f"Error fetching attendance: {str(e)}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            
            data = request.data.copy()
            qr_data = data.get('qr_data', '')
            
            if qr_data:
                try:
                    import json
                    qr_json = json.loads(qr_data)
                    data['student_lrn'] = qr_json.get('lrn', '')
                    if not data.get('student_name'):
                        data['student_name'] = qr_json.get('student', 'Unknown')
                except:
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


# -----------------------------
# ABSENCE, DROPOUT, UNAUTHORIZED PERSON views
# -----------------------------
# (Keeping your previous AbsenceView, DropoutView, UnauthorizedPersonView sections unchanged)


# -----------------------------
# PUBLIC ATTENDANCE LIST
# -----------------------------
class PublicAttendanceListView(generics.ListAPIView):
    queryset = Attendance.objects.all().order_by('-timestamp')
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []


# -----------------------------
# GENERATE SF2 WITH HALF TRIANGLES
# -----------------------------
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_sf2_excel(request):
    # ... your existing SF2 generation code unchanged ...
    pass


# -----------------------------
# GENERATE HALF TRIANGLE EXCEL (NEW)
# -----------------------------
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def generate_half_triangle_excel(request):
    """
    Simple test endpoint that generates an Excel file with a half-triangle shape (for WPS/Excel rendering).
    """
    # Create workbook and sheet
    wb = Workbook()
    ws = wb.active
    ws.title = "Half Triangle Example"

    ws['A1'] = "Half Triangle Shape Demo"

    # Create triangle polygon
    tri = Polygon()
    tri.points = [(0, 0), (0, 1000000), (1000000, 0)]
    tri.fill = SolidFill(srgbClr="FF0000")  # red color

    # Create a drawing container
    drawing = SpreadsheetDrawing()

    # Define position and size of the shape
    shape = XDRShape()
    shape.xfrm.off = XDRPoint2D(0, 0)
    shape.xfrm.ext = XDRPositiveSize2D(2000000, 2000000)
    shape.spPr = tri

    # Add shape to drawing
    drawing.shapes.append(shape)
    ws._drawing = drawing

    # Save to memory
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return FileResponse(
        buffer,
        as_attachment=True,
        filename="half_triangle.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# -----------------------------
# CUSTOM ERROR HANDLER
# -----------------------------
def custom_error_handler(exc, context):
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

# views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import FileResponse
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Alignment, Font
import io

@api_view(['GET'])
def generate_half_triangle_excel(request):
    # Create workbook and worksheet
    wb = Workbook()
    ws = wb.active
    ws.title = "Half Triangle Demo"

    # Set column width
    ws.column_dimensions['A'].width = 20

    # Define red fill
    red_fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")

    # Add a half-triangle illusion using Unicode
    ws["A1"].value = "▲ AM"
    ws["A1"].fill = red_fill
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws["A1"].font = Font(color="FFFFFF", bold=True)

    ws["A2"].value = "▼ PM"
    ws["A2"].fill = red_fill
    ws["A2"].alignment = Alignment(horizontal="center", vertical="center")
    ws["A2"].font = Font(color="FFFFFF", bold=True)

    # Save to BytesIO buffer
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    # Return Excel file
    return FileResponse(buffer, as_attachment=True, filename="half_triangle.xlsx")

