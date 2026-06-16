import os
import json
import re
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# ── 1. Compute Mon-Fri dates for the current week ──────────────────────────
today = datetime.today()
monday = today - timedelta(days=today.weekday())
week_dates = [monday + timedelta(days=i) for i in range(5)]

week_label  = f"{monday.strftime('%B %d')} - {week_dates[4].strftime('%d, %Y')}"
date_header = f"{monday.strftime('%B %d')} - {week_dates[4].strftime('%d, %Y')} "

print(f"Generating report for week: {week_label}")

github_env = os.environ.get("GITHUB_ENV", "")
if github_env:
    with open(github_env, "a") as f:
        f.write(f"WEEK_LABEL={week_label}\n")

# ── 2. Connect to Google Sheets and read leave data ────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

creds_json     = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
spreadsheet_id = os.environ.get("SPREADSHEET_ID", "")

# leave_map = { "Adolf": { 0: "On Leave" }, "Rosee": { 0: "Sick Leave" } ... }
leave_map = {}

def parse_leave_type(text, name_part):
    """
    Detect leave type from a calendar cell entry.
    - bare name only              → On Leave
    - name -SL / Sick             → Sick Leave
    - name (Half Day) / -HL       → Half Day
    - name -EL / Emergency Leave  → Emergency Leave
    - anything else               → On Leave
    """
    rest = text[len(name_part):].strip(" \t-–()")
    rest_up = rest.upper()

    if not rest_up or rest_up == "ON LEAVE":
        return "On Leave"
    elif "EMERGENCY LEAVE" in rest_up or re.search(r'\bEL\b', rest_up):
        return "Emergency Leave"
    elif re.search(r'\bSL\b', rest_up) or "SICK" in rest_up:
        return "Sick Leave"
    elif re.search(r'\bHL\b', rest_up) or "HALF" in rest_up:
        return "Half Day"
    else:
        return "On Leave"

if creds_json and spreadsheet_id:
    try:
        creds_info = json.loads(creds_json)
        creds      = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        gc         = gspread.authorize(creds)

        month_tab = monday.strftime("%B %Y").upper()
        print(f"Looking for sheet tab: {month_tab}")

        wb_gs = gc.open_by_key(spreadsheet_id)
        try:
            ws_gs = wb_gs.worksheet(month_tab)
        except gspread.exceptions.WorksheetNotFound:
            ws_gs = wb_gs.get_worksheet(0)
            print(f"Tab '{month_tab}' not found, using first sheet.")

        all_values = ws_gs.get_all_values()

        # Map column index → weekday index (0=Mon…4=Fri)
        header_row = all_values[1] if len(all_values) > 1 else []
        col_to_weekday = {}
        for ci, hdr in enumerate(header_row):
            h = hdr.strip().upper()
            if   h == "MONDAY":    col_to_weekday[ci] = 0
            elif h == "TUESDAY":   col_to_weekday[ci] = 1
            elif h == "WEDNESDAY": col_to_weekday[ci] = 2
            elif h == "THURSDAY":  col_to_weekday[ci] = 3
            elif h == "FRIDAY":    col_to_weekday[ci] = 4

        # Target day-of-month → day index
        target_days = {wd.day: idx for idx, wd in enumerate(week_dates)}

        for row in all_values[2:]:
            for ci, cell_text in enumerate(row):
                cell_text = cell_text.strip()
                if not cell_text or ci not in col_to_weekday:
                    continue

                weekday_idx = col_to_weekday[ci]
                lines = [l.strip() for l in cell_text.splitlines() if l.strip()]
                if not lines:
                    continue

                # First line is usually the date number
                date_num  = None
                name_lines = lines
                try:
                    date_num   = int(lines[0])
                    name_lines = lines[1:]
                except ValueError:
                    pass

                if date_num not in target_days:
                    continue

                day_idx = target_days[date_num]

                for nl in name_lines:
                    if not nl:
                        continue
                    name_match = re.match(r"^([A-Za-z]+)", nl)
                    if not name_match:
                        continue
                    raw_name   = name_match.group(1).strip()
                    leave_type = parse_leave_type(nl, raw_name)

                    if raw_name not in leave_map:
                        leave_map[raw_name] = {}
                    leave_map[raw_name][day_idx] = leave_type
                    print(f"  Found: {raw_name} | {week_dates[day_idx].strftime('%A')} | {leave_type}")

    except Exception as e:
        print(f"Warning: Could not read Google Sheet – {e}")
else:
    print("No Google credentials found, skipping leave check.")

print(f"\nLeave map: {leave_map}")

# ── 3. Build the Excel report ──────────────────────────────────────────────
wb = load_workbook("template_base.xlsx")

sheets_config = [
    ("SEO Template", ["James", "Jone", "Bernard", "Ken"]),
    ("RTEMPLATE",    ["Rosee", "Nicole"]),
    ("ADTemplate",   ["Adolf"]),
    ("DSTEMPLATE",   ["Kae", "Charles"]),
]

# Day index → Excel column letter (Mon=B … Fri=F)
DAY_COL = {0: "B", 1: "C", 2: "D", 3: "E", 4: "F"}

# Leave type → background fill color
LEAVE_COLORS = {
    "On Leave":        "D9E1F2",  # light blue
    "Sick Leave":      "FFD9D9",  # light red
    "Half Day":        "FFF2CC",  # light yellow
    "Emergency Leave": "F4CCFF",  # light purple
}

for template_name, names in sheets_config:
    for name in names:
        new_ws = wb.copy_worksheet(wb[template_name])
        new_ws.title = name

        new_ws["A10"] = name
        new_ws["C3"]  = date_header

        if template_name == "SEO Template":
            date_cells = ["L13", "L14", "L15", "L16", "L17"]
        else:
            date_cells = ["L8", "L9", "L10", "L11", "L12"]

        for i, cell_addr in enumerate(date_cells):
            new_ws[cell_addr] = week_dates[i]

        new_ws.column_dimensions["A"].width = 28

        # ── Apply leave markings ──────────────────────────────────────
        # Row 13 in all templates = percentage row (B13:F13)
        # We overwrite that cell with leave text + color for affected days
        person_leaves = {}
        for lname, ldays in leave_map.items():
            if lname.lower() == name.lower():
                person_leaves = ldays
                break

        for day_idx, leave_type in person_leaves.items():
            col = DAY_COL.get(day_idx)
            if not col:
                continue

            cell = new_ws[f"{col}13"]
            cell.value = leave_type
            color = LEAVE_COLORS.get(leave_type, "D9E1F2")
            cell.fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
            cell.font = Font(bold=True)
            print(f"  Marked {name} → {col}13 = '{leave_type}'")

wb.save("weekly_report.xlsx")
print("\nReport saved as weekly_report.xlsx ✅")
