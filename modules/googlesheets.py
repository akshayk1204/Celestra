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
        
        try:
            from gspread_formatting import (
                CellFormat, TextFormat, Color,
                format_cell_range, set_column_widths,
                cellFormat, numberFormat
            )
            self.formatting = True
            # Header format
            self.header_fmt = CellFormat(
                textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=Color(1, 1, 1)),
                backgroundColor=Color(0.2, 0.4, 0.6),
                horizontalAlignment='CENTER'
            )
            # Email highlight format
            self.email_fmt = CellFormat(
                backgroundColor=Color(0.9, 1, 0.9),  # Light green
                textFormat=TextFormat(foregroundColor=Color(0, 0.5, 0))  # Dark green
            )
            # Phone highlight format
            self.phone_fmt = CellFormat(
                backgroundColor=Color(0.9, 0.9, 1),  # Light blue
                textFormat=TextFormat(foregroundColor=Color(0, 0, 0.8))  # Dark blue
            )
        except ImportError:
            self.formatting = False
            print("gspread_formatting not available - formatting will be limited")

    def _get_monthly_tab_name(self):
        """Generates the current month-year as the tab name (e.g., 'April 2025')."""
        now = datetime.now()
        return now.strftime("%B %Y")

    def _format_header(self, worksheet):
        """Apply formatting to the header row with updated column widths."""
        if not self.formatting:
            return
            
        try:
            from gspread_formatting import (
                format_cell_range, set_column_widths,
                cellFormat, numberFormat
            )
            
            # Format header row
            format_cell_range(worksheet, '1:1', self.header_fmt)
            worksheet.freeze(rows=1)
            
            # Set column widths - adjusted for better contact info visibility
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
                ('K:K', 150),    # Contact Phone (wider)
                ('L:L', 200),    # Contact Email (wider)
                ('M:M', 150),    # LinkedIn URL
                ('N:N', 100)     # Source
            ])
            
            # Format date column
            date_fmt = cellFormat(
                numberFormat=numberFormat('DATE', 'yyyy-mm-dd')
            )
            format_cell_range(worksheet, 'A2:A1000', date_fmt)
            
            # Highlight valid email and phone cells
            format_cell_range(worksheet, 'L2:L1000', {
                "condition": {
                    "type": "TEXT_CONTAINS",
                    "values": [{"userEnteredValue": "@"}]
                },
                "format": self.email_fmt
            })
            
            format_cell_range(worksheet, 'K2:K1000', {
                "condition": {
                    "type": "TEXT_CONTAINS",
                    "values": [{"userEnteredValue": "+"}]
                },
                "format": self.phone_fmt
            })
            
        except Exception as e:
            print(f"Header formatting failed (non-critical): {e}")

    def export_incidents(self, incidents: List[Dict]) -> bool:
        if not incidents:
            print("No incidents to export.")
            return False

        try:
            # Convert to DataFrame and clean data
            df = pd.DataFrame(incidents)
            
            # Clean contact information
            df['Contact Email'] = df['Contact Email'].apply(
                lambda x: x if isinstance(x, str) and "@" in x else "Not Available"
            )
            df['Contact Phone'] = df['Contact Phone'].apply(
                lambda x: x if isinstance(x, str) and x.replace("+", "").isdigit() else "Not Available"
            )
            
            # Define column order with contact info prioritized
            column_order = [
                'Date of Breach',
                'Company Name',
                'Company Website',
                'Contact Name',
                'Contact Title',
                'Contact Phone',  # Moved up
                'Contact Email',  # Moved up
                'Company Size',
                'Type of Breach',
                'CDN',
                'Security',
                'Country',
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

            # Clear and update data - ensure all values are strings
            worksheet.clear()
            data = df.fillna('').astype(str).values.tolist()
            worksheet.update([df.columns.tolist()] + data)

            # Apply formatting
            if self.formatting:
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