import os
import shutil
from openpyxl import load_workbook
from datetime import datetime, timedelta

# --- Compute the current week's Monday-Friday ---
today = datetime.today()
# Get the most recent Monday
monday = today - timedelta(days=today.weekday())
week_dates = [monday + timedelta(days=i) for i in range(5)]

week_label = f"{monday.strftime('%B %d')} - {week_dates[4].strftime('%d, %Y')}"
date_header = f"{monday.strftime('%B %d')} - {week_dates[4].strftime('%d, %Y')} "

print(f"Generating report for week: {week_label}")

# Write week label to env for the email subject
with open(os.environ.get("GITHUB_ENV", "/dev/null"), "a") as f:
    f.write(f"WEEK_LABEL={week_label}\n")

# --- Load the base template file ---
wb = load_workbook("template_base.xlsx")

# --- Config: which template to copy and what name to use ---
sheets_config = [
    ("SEO Template", ["James", "Jone", "Bernard", "Ken"]),
    ("RTEMPLATE",    ["Rosee", "Nicole"]),
    ("ADTemplate",   ["Adolf"]),
    ("DSTEMPLATE",   ["Kae", "Charles"]),
]

for template_name, names in sheets_config:
    for name in names:
        new_ws = wb.copy_worksheet(wb[template_name])
        new_ws.title = name

        # Update NAME cell
        new_ws["A10"] = name

        # Update date header
        new_ws["C3"] = date_header

        # Update individual date cells
        date_cells = ["L8", "L9", "L10", "L11", "L12"]
        # SEO Template uses different rows
        if template_name == "SEO Template":
            date_cells = ["L13", "L14", "L15", "L16", "L17"]

        for i, cell_addr in enumerate(date_cells):
            new_ws[cell_addr] = week_dates[i]

        # Fix column A width to avoid ### display
        new_ws.column_dimensions["A"].width = 28

wb.save("weekly_report.xlsx")
print("Report saved as weekly_report.xlsx")
