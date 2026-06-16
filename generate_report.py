import os
import json
import re
from openpyxl import load_workbook
from openpyxl.styles import PatternFill
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# ── 1. Compute Mon-Fri dates for the current week ──────────────────────────
today = datetime.today()
monday = today - timedelta(days=today.weekday())
week_dates = [monday + timedelta(days=i) for i in range(5)]  # Mon-Fri

week_label    = f"{monday.strftime('%B %d')} - {week_dates[4].strftime('%d, %Y')}"
date_header   = f"{monday.strftime('%B %d')} - {week_dates[4].strftime('%d, %Y')} "

print(f"Generating report for week: {week_label}")

# Write week label to GitHub env for the email subject
github_env = os.environ.get("GITHUB_ENV", "")
if github_env:
    with open(github_env, "a") as f:
        f.write(f"WEEK_LABEL={week_label}\n")

# ── 2. Connect to Google Sheets and read leave data ────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

creds_json  = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
spreadsheet_id = os.environ.get("SPREADSHEET_ID", "")

leave_map = {}  # { "Rosee": { 0: "Sick Leave", 2: "Half Day" }, ... }
                # key = day index (0=Mon ... 4=Fri)

if creds_json and spreadsheet_id:
    try:
        creds_info = json.loads(creds_json)
        creds      = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        gc         = gspread.authorize(creds)

        # Open the sheet tab matching the current month/year e.g. "JUNE 2026"
        month_tab = monday.strftime("%B %Y").upper()
        print(f"Looking for sheet tab: {month_tab}")

        wb_gs  = gc.open_by_key(spreadsheet_id)
        try:
            ws_gs  = wb_gs.worksheet(month_tab)
        except gspread.exceptions.WorksheetNotFound:
            # Fallback: try the first sheet
            ws_gs = wb_gs.get_worksheet(0)
            print(f"Tab '{month_tab}' not found, using first sheet.")

        all_values = ws_gs.get_all_values()

        # ── Parse the calendar grid ──────────────────────────────────────
        # Row 2 (index 1) = day-of-week headers
        # Columns are: A=Sun B=Mon C=Tue D=Wed E=Thu F=Fri G=Sat  (0-indexed: 0-6)
        # We map column index → weekday (0=Mon … 4=Fri), ignoring Sun/Sat
        header_row = all_values[1] if len(all_values) > 1 else []
        col_to_weekday = {}
        for ci, hdr in enumerate(header_row):
            h = hdr.strip().upper()
            if h == "MONDAY":    col_to_weekday[ci] = 0
            elif h == "TUESDAY":  col_to_weekday[ci] = 1
            elif h == "WEDNESDAY":col_to_weekday[ci] = 2
            elif h == "THURSDAY": col_to_weekday[ci] = 3
            elif h == "FRIDAY":   col_to_weekday[ci] = 4

        # Target dates (day-of-month numbers for this Mon-Fri)
        target_days = {wd.day: idx for idx, wd in enumerate(week_dates)}
        # e.g. {8:0, 9:1, 10:2, 11:3, 12:4}

        def parse_leave_type(text, name_part):
            """Return leave label from the cell text after stripping the name."""
            rest = text[len(name_part):].strip(" -").upper()
            if "EMERGENCY LEAVE" in rest or rest == "EL":
                return "Emergency Leave"
            elif "SL" in rest:
                return "Sick Leave"
            elif "HL" in rest or "HALF" in rest:
                return "Half Day"
            elif "ON LEAVE" in rest or rest == "":
                return "On Leave"
            else:
                return "On Leave"

        # Scan every data row (skip rows 0-1 = title + header)
        for row in all_values[2:]:
            for ci, cell_text in enumerate(row):
                cell_text = cell_text.strip()
                if not cell_text:
                    continue
                if ci not in col_to_weekday:
                    continue
                weekday_idx = col_to_weekday[ci]

                # Split cell by newline – first token is usually the date number
                lines = [l.strip() for l in cell_text.splitlines() if l.strip()]
                if not lines:
                    continue

                # First line may be just a number (the date)
                date_num = None
                name_lines = lines
                try:
                    date_num = int(lines[0])
                    name_lines = lines[1:]
                except ValueError:
                    pass

                if date_num not in target_days:
                    continue

                day_idx = target_days[date_num]  # 0-4

                for nl in name_lines:
                    if not nl:
                        continue
                    # Extract name (everything before a suffix marker)
                    # e.g. "Rosee -SL", "Jone (Half-day)", "Bernard"
                    name_match = re.match(r"^([A-Za-z]+)", nl)
                    if not name_match:
                        continue
                    raw_name = name_match.group(1).strip()
                    leave_type = parse_leave_type(nl, raw_name)

                    if raw_name not in leave_map:
                        leave_map[raw_name] = {}
                    leave_map[raw_name][day_idx] = leave_type
                    print(f"  Found: {raw_name} on day {day_idx} ({week_dates[day_idx].strftime('%A')}) → {leave_type}")

    except Exception as e:
        print(f"Warning: Could not read Google Sheet – {e}")
else:
    print("No Google credentials found, skipping leave check.")

print(f"\nLeave map: {leave_map}")

# ── 3. Load base template and build the Excel report ──────────────────────
wb = load_workbook("template_base.xlsx")

sheets_config = [
    ("SEO Template", ["James", "Jone", "Bernard", "Ken"]),
    ("RTEMPLATE",    ["Rosee", "Nicole"]),
    ("ADTemplate",   ["Adolf"]),
    ("DSTEMPLATE",   ["Kae", "Charles"]),
]

# Day index → column letter in Excel (row 13 = leave row)
# Based on screenshot: Mon=B, Tue=C, Wed=D, Thu=E, Fri=F
DAY_COL = {0: "B", 1: "C", 2: "D", 3: "E", 4: "F"}

# Leave type → fill color (light tones)
LEAVE_COLORS = {
    "Sick Leave":       "FFD9D9",   # light red
    "On Leave":         "D9E1F2",   # light blue
    "Half Day":         "FFF2CC",   # light yellow
    "Emergency Leave":  "F4CCFF",   # light purple
}

for template_name, names in sheets_config:
    for name in names:
        new_ws = wb.copy_worksheet(wb[template_name])
        new_ws.title = name

        new_ws["A10"] = name
        new_ws["C3"]  = date_header

        # Date cells differ per template
        if template_name == "SEO Template":
            date_cells = ["L13", "L14", "L15", "L16", "L17"]
        else:
            date_cells = ["L8", "L9", "L10", "L11", "L12"]

        for i, cell_addr in enumerate(date_cells):
            new_ws[cell_addr] = week_dates[i]

        new_ws.column_dimensions["A"].width = 28

        # ── Apply leave markings ──────────────────────────────────────
        # Find this person in leave_map (case-insensitive match)
        person_leaves = {}
        for lname, ldays in leave_map.items():
            if lname.lower() == name.lower():
                person_leaves = ldays
                break

        for day_idx, leave_type in person_leaves.items():
            col = DAY_COL.get(day_idx)
            if not col:
                continue

            # Row 13 = leave label row (same for all templates based on screenshot)
            cell = new_ws[f"{col}13"]
            cell.value = leave_type

            # Apply background color
            color = LEAVE_COLORS.get(leave_type, "FFD9D9")
            cell.fill = PatternFill(start_color=color, end_color=color, fill_type="solid")

            print(f"  Marked {name} sheet: {col}13 = '{leave_type}'")

wb.save("weekly_report.xlsx")
print("\nReport saved as weekly_report.xlsx ✅")
