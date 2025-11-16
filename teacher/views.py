from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.http import FileResponse
from rest_framework import generics, permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from .models import TeacherProfile, Attendance, UnauthorizedPerson
from .serializers import (
    TeacherProfileSerializer, 
    AttendanceSerializer,
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

# -----------------------------
# TEACHER REGISTRATION (Public)
# -----------------------------
class RegisterView(generics.CreateAPIView):
    queryset = TeacherProfile.objects.all()
    serializer_class = TeacherProfileSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        data = request.data
        try:
            # Step 1: Create the User first
            username = data.get("name").replace(" ", "").lower()
            password = data.get("password")

            if not password:
                return Response({"error": "Password is required."}, status=status.HTTP_400_BAD_REQUEST)

            if User.objects.filter(username=username).exists():
                return Response({"error": "Username already exists."}, status=status.HTTP_400_BAD_REQUEST)

            user = User.objects.create_user(username=username, password=password)
            user.first_name = data.get("name")
            user.save()

            # Step 2: Create the TeacherProfile
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            teacher_profile = serializer.save(user=user)  # Pass the User object

            # Step 3: Generate token
            token, _ = Token.objects.get_or_create(user=user)

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
            return Response({"error": "Username already exists."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Registration failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            

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

            if not data.get('session'):
                now = datetime.now()
                ph_time = now.astimezone(ZoneInfo('Asia/Manila'))
                data['session'] = 'AM' if ph_time.hour < 12 else 'PM'

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
# BULK ATTENDANCE UPDATE
# -----------------------------
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def bulk_update_attendance(request):
    """
    Bulk update attendance records.
    
    Expected payload:
    {
        "updates": [
            {
                "id": 1,
                "status": "Absent"
            },
            {
                "id": 2,
                "status": "Dropped Out",
                "reason": "Transferred to another school"
            }
        ]
    }
    """
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
        updates = request.data.get('updates', [])
        
        if not updates:
            return Response(
                {"error": "No updates provided"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        results = {
            'updated': [],
            'errors': []
        }
        
        for update_data in updates:
            try:
                attendance_id = update_data.get('id')
                new_status = update_data.get('status')
                
                if not attendance_id or not new_status:
                    results['errors'].append({
                        'id': attendance_id,
                        'error': 'Missing id or status'
                    })
                    continue
                
                attendance = Attendance.objects.get(pk=attendance_id, teacher=teacher_profile)
                
                if 'status' in update_data:
                    attendance.status = new_status
                if 'gender' in update_data:
                    attendance.gender = update_data['gender']
                if 'session' in update_data:
                    attendance.session = update_data['session']
                if 'date' in update_data:
                    attendance.date = update_data['date']
                if 'student_name' in update_data:
                    attendance.student_name = update_data['student_name']
                if 'student_lrn' in update_data:
                    attendance.student_lrn = update_data['student_lrn']
                if 'reason' in update_data:
                    attendance.reason = update_data['reason']
                
                attendance.save()
                results['updated'].append({
                    'id': attendance_id,
                    'student_name': attendance.student_name,
                    'status': attendance.status
                })
                
            except Attendance.DoesNotExist:
                results['errors'].append({
                    'id': attendance_id,
                    'error': 'Attendance record not found'
                })
            except Exception as e:
                results['errors'].append({
                    'id': attendance_id,
                    'error': str(e)
                })
        
        return Response({
            'message': 'Bulk update completed',
            'results': results
        }, status=status.HTTP_200_OK)
        
    except TeacherProfile.DoesNotExist:
        return Response(
            {"error": "Teacher profile not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return Response(
            {"error": f"Bulk update failed: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

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

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_sf2_excel(request):
    """
    Generate SF2 Excel report with attendance data for a specific month.
    Separates students by gender: Boys start at row 14, Girls start at row 36.
    ONLY WEEKDAYS (Monday-Friday) are included in the calendar.
    Students with status "Dropped Out" are excluded from the report.
    
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
        teacher_profile = TeacherProfile.objects.get(user=request.user)

        template_file = request.FILES.get('template_file')
        if not template_file:
            return Response(
                {"error": "Please upload an SF2 template file."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            wb = load_workbook(template_file)
        except Exception as e:
            return Response(
                {"error": f"Failed to load Excel template: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            month = int(request.POST.get('month', datetime.now().month))
            year = int(request.POST.get('year', datetime.now().year))
        except ValueError:
            return Response(
                {"error": "Invalid month or year parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if month < 1 or month > 12:
            return Response(
                {"error": "Month must be between 1 and 12"},
                status=status.HTTP_400_BAD_REQUEST
            )

        month_names = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", 
                      "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        
        day_names_short = ["Mon", "Tue", "Wed", "Thu", "Fri"]

        # Exclude students with "Dropped Out" status
        attendances = Attendance.objects.filter(
            teacher=teacher_profile,
            date__year=year,
            date__month=month
        ).exclude(status='Dropped Out').order_by('date', 'timestamp')

        print(f"📊 Fetching attendance for: {month_names[month-1]} {year}")
        print(f"📝 Found {attendances.count()} attendance records (excluding dropped out students)")

        attendance_data = defaultdict(
            lambda: {'days': defaultdict(lambda: {'am': False, 'pm': False}), 'gender': None}
        )
        
        students_dict = {}

        for att in attendances:
            student_name = att.student_name
            day = att.date.day
            
            if student_name not in students_dict:
                students_dict[student_name] = att.gender if hasattr(att, 'gender') and att.gender else 'Male'
            
            if hasattr(att, 'session') and att.session:
                session = att.session.upper()
            elif att.timestamp:
                from zoneinfo import ZoneInfo
                ph_time = att.timestamp.astimezone(ZoneInfo('Asia/Manila'))
                session = 'AM' if ph_time.hour < 12 else 'PM'
            else:
                session = 'AM'

            if att.status and att.status.lower() not in ['absent', 'dropped out']:
                if session == 'AM':
                    attendance_data[student_name]['days'][day]['am'] = True
                elif session == 'PM':
                    attendance_data[student_name]['days'][day]['pm'] = True
            
            attendance_data[student_name]['gender'] = students_dict[student_name]

        boys = sorted([name for name, gender in students_dict.items() if gender and gender.lower() == 'male'])
        girls = sorted([name for name, gender in students_dict.items() if gender and gender.lower() == 'female'])
        
        print(f"👦 Boys: {len(boys)} students")
        print(f"👧 Girls: {len(girls)} students")

        now = datetime.now()
        current_day = now.day
        current_year = now.year
        current_month = now.month

        red_fill = PatternFill(start_color='FF0000', end_color='FF0000', fill_type='solid')
        green_fill = PatternFill(start_color='00B050', end_color='00B050', fill_type='solid')
        
        triangle_font = Font(color="00B050", size=48, bold=True)
        
        center_alignment = Alignment(horizontal='center', vertical='center')
        left_alignment = Alignment(horizontal='left', vertical='center')
        
        am_triangle_alignment = Alignment(
            horizontal='justify',
            vertical='center',
            wrap_text=False,
            shrink_to_fit=False
        )
        
        pm_triangle_alignment = Alignment(
            horizontal='left',
            vertical='center',
            wrap_text=False,
            shrink_to_fit=False
        )

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
        
        date_row = 11
        day_row = 12
        boys_start_row = 14
        girls_start_row = 36
        
        name_column = 2
        first_day_column = 4

        def unmerge_and_write(ws, row, col, value, alignment=None):
            from openpyxl.cell.cell import MergedCell
            
            cell_coord = ws.cell(row=row, column=col).coordinate
            
            for merged_range in list(ws.merged_cells.ranges):
                if cell_coord in merged_range:
                    ws.unmerge_cells(str(merged_range))
                    print(f"    🔓 Unmerged {merged_range}")
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
                print(f"    ❌ Error writing to {cell_coord}: {e}")
                
            return cell

        days_in_month = monthrange(year, month)[1]
        print(f"📅 Days in {month_name} {year}: {days_in_month}")

        day_columns = {}
        from datetime import date
        
        print("\n📅 Filling weekday calendar headers (only Mon-Fri)...")
        current_col = first_day_column
        
        for day in range(1, days_in_month + 1):
            current_date = date(year, month, day)
            day_of_week = current_date.weekday()
            
            if day_of_week < 5:
                day_columns[day] = current_col
                
                unmerge_and_write(ws, date_row, current_col, day, center_alignment)
                
                day_name = day_names_short[day_of_week]
                unmerge_and_write(ws, day_row, current_col, day_name, center_alignment)
                
                print(f"    Day {day:2d} ({current_date.strftime('%Y-%m-%d')}): {day_name} at column {current_col}")
                current_col += 1
            else:
                day_name_full = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][day_of_week]
                print(f"    Day {day:2d} ({current_date.strftime('%Y-%m-%d')}): {day_name_full} WEEKEND - SKIPPED")
        
        print(f"✓ Filled {len(day_columns)} weekday columns")

        def is_merged_cell(ws, row, col):
            from openpyxl.cell.cell import MergedCell
            cell = ws.cell(row=row, column=col)
            return isinstance(cell, MergedCell)

        def fill_student_attendance(students_list, start_row):
            filled_count = 0
            for idx, name in enumerate(students_list):
                row_num = start_row + idx
                
                print(f"  Processing student: {name} at row {row_num}")
                
                unmerge_and_write(ws, row_num, name_column, name, left_alignment)

                for day, col_idx in day_columns.items():
                    if year == current_year and month == current_month and day > current_day:
                        continue

                    try:
                        if is_merged_cell(ws, row_num, col_idx):
                            print(f"    ⏭️ Skipping merged cell at row {row_num}, col {col_idx}")
                            continue
                            
                        cell = ws.cell(row=row_num, column=col_idx)
                        
                        has_am = attendance_data[name]['days'][day]['am']
                        has_pm = attendance_data[name]['days'][day]['pm']

                        cell.value = None
                        cell.fill = PatternFill(fill_type=None)
                        cell.font = Font()
                        cell.alignment = center_alignment

                        if not has_am and not has_pm:
                            cell.fill = red_fill
                            cell.alignment = center_alignment
                            filled_count += 1

                        elif has_am and has_pm:
                            cell.fill = green_fill
                            cell.alignment = center_alignment
                            filled_count += 1

                        elif has_am and not has_pm:
                            cell.value = "◤"
                            cell.font = triangle_font
                            cell.alignment = am_triangle_alignment
                            filled_count += 1
                            print(f"    ✓ AM triangle (◤) for day {day}: Middle+Justify")
                            
                        elif has_pm and not has_am:
                            cell.value = "◢"
                            cell.font = triangle_font
                            cell.alignment = pm_triangle_alignment
                            filled_count += 1
                            print(f"    ✓ PM triangle (◢) for day {day}: Middle+Left")
                            
                    except Exception as e:
                        print(f"    ❌ Error filling day {day}: {e}")
                        
            return filled_count

        print(f"\n👦 Filling boys section starting at row {boys_start_row}")
        boys_filled = fill_student_attendance(boys, boys_start_row)
        print(f"✓ Filled {boys_filled} cells for boys")
        
        print(f"\n👧 Filling girls section starting at row {girls_start_row}")
        girls_filled = fill_student_attendance(girls, girls_start_row)
        print(f"✓ Filled {girls_filled} cells for girls")

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        filename = f"SF2_{month_name}_{year}_{teacher_profile.section.replace(' ', '_')}.xlsx"
        
        print(f"\n✅ SF2 generated successfully: {filename}")
        print(f"📊 Total cells filled: {boys_filled + girls_filled}")
        
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
        print("=" * 80)
        print("SF2 Generation Error:")
        print(error_trace)
        print("=" * 80)
        
        return Response(
            {"error": f"Failed to generate SF2 Excel: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
