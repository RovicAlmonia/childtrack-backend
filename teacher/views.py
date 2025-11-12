# views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import FileResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Side, Font, PatternFill
import io

@api_view(['GET'])
def generate_sf2_excel(request):
    wb = Workbook()
    ws = wb.active
    ws.title = "SF2"

    # --- HEADER SECTION ---
    ws.merge_cells('A1:AF1')
    ws['A1'] = "SCHOOL FORM 2 (SF2) DAILY ATTENDANCE REPORT OF LEARNERS"
    ws['A1'].font = Font(size=14, bold=True)
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')

    ws['A3'] = "School:"
    ws['E3'] = "Month:"
    ws['J3'] = "Grade & Section:"
    ws['O3'] = "Teacher:"
    ws['T3'] = "School Year:"

    # --- COLUMN HEADERS ---
    ws['A5'] = "No."
    ws['B5'] = "LRN"
    ws['C5'] = "NAME OF LEARNERS (Last Name, First Name, Name Extension, Middle Name)"
    col = 4
    for day in range(1, 32):
        ws.cell(row=5, column=col, value=day)
        col += 1
    ws.cell(row=5, column=col, value="Total Absent")
    ws.cell(row=5, column=col+1, value="Total Present")
    ws.cell(row=5, column=col+2, value="Remarks")

    # --- SAMPLE DATA ---
    learners = [
        {"no": 1, "lrn": "123456789012", "name": "Dela Cruz, Juan A."},
        {"no": 2, "lrn": "123456789013", "name": "Reyes, Maria B."},
        {"no": 3, "lrn": "123456789014", "name": "Santos, Pedro C."},
    ]

    row = 6
    for learner in learners:
        ws[f"A{row}"] = learner["no"]
        ws[f"B{row}"] = learner["lrn"]
        ws[f"C{row}"] = learner["name"]
        # Fill attendance sample (✓ = present, X = absent)
        for d in range(1, 32):
            ws.cell(row=row, column=3+d, value="✓" if d % 6 != 0 else "X")
        ws.cell(row=row, column=36, value=4)   # Total Absent
        ws.cell(row=row, column=37, value=27)  # Total Present
        ws.cell(row=row, column=38, value="Good")
        row += 1

    # --- FORMATTING ---
    thin = Side(border_style="thin", color="000000")
    border = Border(top=thin, left=thin, right=thin, bottom=thin)

    for r in ws.iter_rows(min_row=5, max_row=row-1, min_col=1, max_col=38):
        for cell in r:
            cell.border = border
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            if cell.row == 5:
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")

    ws.column_dimensions['A'].width = 4
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 40
    for col in range(4, 39):
        ws.column_dimensions[chr(64 + col if col < 27 else 64 + (col - 26))].width = 4

    # --- FOOTER ---
    ws.merge_cells(f"A{row+2}:J{row+2}")
    ws[f"A{row+2}"] = "Prepared by:"
    ws[f"A{row+2}"].font = Font(bold=True)

    # --- SAVE TO BUFFER ---
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return FileResponse(buffer, as_attachment=True, filename="SF2_Report.xlsx")
