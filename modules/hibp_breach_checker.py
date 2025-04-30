import requests
import json
import os
from datetime import datetime
from pathlib import Path
from googlesheets import GoogleSheetsExporter
from config.settings import HIPB_KEY

class HIBPBreachFetcher:
    def __init__(self):
        self.api_key = HIPB_KEY
        self.data_dir = Path(__file__).resolve().parent / "data"
        self.last_checked_file = self.data_dir / "last_checked.json"
        self.endpoint = "https://haveibeenpwned.com/api/v3/breaches"
        self.headers = {
            "hibp-api-key": self.api_key,
            "user-agent": "CelestraBreachMonitor/1.0"
        }
        self.sheets_exporter = GoogleSheetsExporter()

    def load_last_checked_date(self):
        if self.last_checked_file.exists():
            with open(self.last_checked_file, "r") as f:
                return datetime.strptime(json.load(f).get("last_breach_date"), "%Y-%m-%d")
        return datetime.strptime("2000-01-01", "%Y-%m-%d")

    def save_last_checked_date(self, date_str):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with open(self.last_checked_file, "w") as f:
            json.dump({"last_breach_date": date_str}, f)

    def fetch_all_breaches(self):
        response = requests.get(self.endpoint, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def convert_to_incident_format(self, breach):
        return {
            "date": breach["BreachDate"],
            "title": breach["Title"],
            "source": "HIBP",
            "source_url": f"https://haveibeenpwned.com/PwnedWebsites#{breach['Name']}",
            "organizations": [breach["Domain"]] if breach.get("Domain") else [],
            "raw_content": f"Name: {breach['Name']}\nDomain: {breach.get('Domain', '')}\nData: {', '.join(breach.get('DataClasses', []))}",
            "compromised_data": breach.get("DataClasses", []),
            "country": "",
            "categories": ["breach"],
            "record_count": breach.get("PwnCount", "")
        }

    def run(self):
        last_date = self.load_last_checked_date()
        breaches = self.fetch_all_breaches()
        new_breaches = [
            b for b in breaches
            if datetime.strptime(b["BreachDate"], "%Y-%m-%d") > last_date
        ]

        if not new_breaches:
            print("No new breaches found.")
            return

        incidents = [self.convert_to_incident_format(b) for b in new_breaches]
        self.sheets_exporter.export_incidents(incidents)

        most_recent = max(datetime.strptime(b["BreachDate"], "%Y-%m-%d") for b in new_breaches)
        self.save_last_checked_date(most_recent.strftime("%Y-%m-%d"))
        print(f"Exported {len(incidents)} new breaches to Google Sheets.")

if __name__ == "__main__":
    HIBPBreachFetcher().run()
