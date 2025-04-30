import pandas as pd
from datetime import datetime
import os
import logging
from typing import List, Dict
from modules.googlesheets import GoogleSheetsExporter

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class B1NDDataset:
    def __init__(self):
        self.data_path = "data/breach_datasets/b1nd_breaches.csv"
        self._ensure_data_directory_exists()
        self.sheets_exporter = GoogleSheetsExporter()

    def _ensure_data_directory_exists(self):
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        logger.info(f"Ensured data directory exists at {self.data_path}")

    def get_all_breaches(self) -> List[Dict]:
        try:
            logger.info("Fetching all breaches from the B1ND dataset...")
            df = pd.read_csv(self.data_path)
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')  # Coerce invalid dates to NaT
            
            # Log number of records
            logger.info(f"Fetched {len(df)} breaches from B1ND dataset.")

            # Display the first few rows as a sample (you can adjust the number here if you need more)
            logger.info("Sample breaches:")
            for index, row in df.head(5).iterrows():
                logger.info(f"Date: {row['Date']} | Domain: {row['Website']} | Company: {row['Website'].split('.')[0]} | Compromised Data: {row['Compromised Data']}")

            return self._parse_to_standard_format(df)
        except Exception as e:
            logger.error(f"Error reading B1ND dataset: {str(e)}")
            return []

    def get_all_incidents(self) -> List[Dict]:
        return self.get_all_breaches()

    def _parse_to_standard_format(self, df: pd.DataFrame) -> List[Dict]:
        logger.info(f"Parsing {len(df)} rows from the dataset into standard format...")
        breaches = []
        for _, row in df.iterrows():
            if pd.isna(row['Date']):  # Skip rows with invalid dates (NaT)
                continue
            
            # Extract year from the 'Date' column (which is a Timestamp object)
            year = row['Date'].year
            formatted_date = f"{year}-01-01"  # Create a full date format as %Y-01-01

            # Extract domain and company name
            domain = row['Website'].strip()
            company = domain.split('.')[0]  # Extract company name from domain (e.g., clubedoingresso.com → clubedoingresso)

            # Extract compromised data
            compromised_data = [x.strip() for x in str(row['Compromised Data']).split(',')]

            breach = {
                'date': formatted_date,  # Using the formatted date
                'title': f"{company} Data Breach",  # Using company name
                'source': 'B1ND',
                'source_url': '',  # URL can be added if available
                'organizations': [domain],  # Using domain directly
                'country': row['Website Country'],
                'compromised_data': compromised_data,  # Direct mapping
                'raw_content': (
                    f"Website: {domain}\n"
                    f"Country: {row['Website Country']}\n"
                    f"Compromised: {', '.join(compromised_data)}"
                ),
                'categories': ['breach'],
                'record_count': row['Record Count']
            }

            breaches.append(breach)

        logger.info(f"Parsed {len(breaches)} breaches.")
        return breaches

    def update_dataset(self, new_file_path: str):
        try:
            logger.info(f"Attempting to update dataset with new file: {new_file_path}")
            test_df = pd.read_csv(new_file_path)
            required_cols = {'Record Count', 'Date', 'Website', 'Website Country', 'Compromised Data'}
            if not required_cols.issubset(test_df.columns):
                logger.error(f"New file missing required columns: {required_cols}")
                raise ValueError("New file missing required columns")

            os.replace(new_file_path, self.data_path)
            with open("data/breach_datasets/last_update.txt", 'w') as f:
                f.write(datetime.now().isoformat())
            logger.info("Dataset updated successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to update dataset: {str(e)}")
            return False

    def export_breaches_to_sheets(self):
        breaches = self.get_all_breaches()
        if breaches:
            logger.info(f"Exporting {len(breaches)} breaches to Google Sheets...")
            for b in breaches:
                b['source'] = 'B1ND'
            success = self.sheets_exporter.export_incidents(breaches)
            if success:
                logger.info(f"Successfully exported {len(breaches)} breaches to Google Sheets.")
            else:
                logger.error("Failed to export breaches to Google Sheets.")
        else:
            logger.warning("No breaches found to export.")
