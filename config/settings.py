import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).parent.parent

# API Keys - with validation
HIPB_KEY = os.environ["HIPB_KEY"]  # Required
APOLLO_API_KEY = os.environ["APOLLO_API_KEY"]  # Required
IPINFO_API_KEY = os.getenv("IPINFO_API_KEY")  # Optional

# Google Sheets configuration
GOOGLE_CREDS_JSON = BASE_DIR / os.environ["GOOGLE_CREDS_JSON"]
if not GOOGLE_CREDS_JSON.exists():
    raise FileNotFoundError(f"Credentials file not found at: {GOOGLE_CREDS_JSON}")

SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
SHEET_NAME = os.environ.get("GOOGLE_SHEET_NAME", "Celestra-Output")

# Incident storage
INCIDENTS_DIR = BASE_DIR / "data" / "incidents"
os.makedirs(INCIDENTS_DIR, exist_ok=True)

# Rate limits
RATE_LIMITS = {
    'apollo': 50,
    'hibp': 30  # HIBP typically has a rate limit of 30 requests/minute
}