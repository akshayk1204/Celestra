import gspread
import pandas as pd
from typing import List, Dict
from datetime import datetime
from google.oauth2.service_account import Credentials
from config.settings import GOOGLE_CREDS_JSON, SHEET_NAME
import os
from gspread_formatting import *

class GoogleSheetsExporter:
    def __init__(self, creds_path=GOOGLE_CREDS_JSON, sheet_name=SHEET_NAME):
        self.scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        self.creds = Credentials.from_service_account_file(creds_path, scopes=self.scope)
        self.client = gspread.authorize(self.creds)
        self.sheet_name = sheet_name
        self.sheet = None
        # Initialize formatting objects if gspread_formatting is available
        try:
            from gspread_formatting import (
                CellFormat,
                TextFormat,
                Color,
                format_cell_range,
                set_column_widths,
                cellFormat,  # Note the lowercase 'c' (this is correct)
                numberFormat
            )
            self.formatting = True
            self.fmt = CellFormat(
                textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=Color(1, 1, 1)),
                backgroundColor=Color(0.2, 0.4, 0.6),
                horizontalAlignment='CENTER'
            )
        except ImportError:
            self.formatting = False
            print("gspread_formatting not available - formatting will be limited")

    def _get_monthly_tab_name(self):
        """Generates the current month-year as the tab name (e.g., 'April 2025')."""
        now = datetime.now()
        return now.strftime("%B %Y")

    def _format_header(self, worksheet):
        """Apply beautiful formatting to the header row with updated column widths."""
        if not self.formatting:
            return
            
        try:
            from gspread_formatting import (
                format_cell_range,
                set_column_widths,
                cellFormat,
                numberFormat
            )
            
            # Format header row (A1:N1)
            format_cell_range(worksheet, '1:1', self.fmt)
            
            # Freeze header row
            worksheet.freeze(rows=1)
            
            # Set column widths for the new column order
            set_column_widths(worksheet, [
                ('A:A', 100),    # Date of Breach
                ('B:B', 200),    # Company Name
                ('C:C', 150),    # Company Website
                ('D:D', 100),    # Company Size
                ('E:E', 150),    # Type of Breach
                ('F:F', 100),    # CDN
                ('G:G', 100),    # Security
                ('H:H', 100),    # Country
                ('I:I', 150),    # Contact Name
                ('J:J', 150),    # Contact Title
                ('K:K', 120),    # Contact Phone
                ('L:L', 150),    # Contact Email
                ('M:M', 150),    # LinkedIn URL
                ('N:N', 100)     # Source
            ])
            
            # Format date column
            date_fmt = cellFormat(
                numberFormat=numberFormat('DATE', 'yyyy-mm-dd')
            )
            format_cell_range(worksheet, 'A2:A1000', date_fmt)
            
        except Exception as e:
            print(f"Header formatting failed (non-critical): {e}")

    def export_incidents(self, incidents: List[Dict]) -> bool:
        if not incidents:
            print("No incidents to export.")
            return False

        try:
            # Convert to DataFrame
            df = pd.DataFrame(incidents)
            
            # Define the desired column order
            column_order = [
                'Date of Breach',
                'Company Name',
                'Company Website',
                'Company Size',
                'Type of Breach',
                'CDN',
                'Security',
                'Country',
                'Contact Name',
                'Contact Title',
                'Contact Phone',
                'Contact Email',
                'LinkedIn URL',
                'Source'
            ]
            
            # Reorder columns and keep only those that exist
            existing_columns = [col for col in column_order if col in df.columns]
            df = df[existing_columns]
            
            # Access the Google Sheet
            self.sheet = self.client.open(self.sheet_name)
            tab_name = self._get_monthly_tab_name()

            # Get or create worksheet
            try:
                worksheet = self.sheet.worksheet(tab_name)
            except gspread.WorksheetNotFound:
                worksheet = self.sheet.add_worksheet(title=tab_name, rows="1000", cols="20")

            # Clear and update data
            df = df.applymap(lambda x: x[0] if isinstance(x, list) and x else x)
            worksheet.clear()
            worksheet.update([df.columns.tolist()] + df.values.tolist())

            # Apply beautiful formatting
            self._format_header(worksheet)

            print(f"Exported {len(df)} incidents to Google Sheet tab '{tab_name}'")
            return True
        except Exception as e:
            print(f"[GoogleSheetsExporter] Export failed: {e}")
            return False

    def get_sheet_url(self):
        """Helper method to safely get the sheet URL."""
        if self.sheet:
            return self.sheet.url
        print("Sheet not opened yet. Please ensure export was successful.")
        return None