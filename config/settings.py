import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Google Sheets configuration - with validation
GOOGLE_CREDS_JSON = BASE_DIR / os.environ["GOOGLE_CREDS_JSON"]  # Will raise clear error if missing
if not GOOGLE_CREDS_JSON.exists():
    raise FileNotFoundError(f"Credentials file not found at: {GOOGLE_CREDS_JSON}")

SHEET_ID = os.environ["GOOGLE_SHEET_ID"]  # Required
SHEET_NAME = os.environ.get("GOOGLE_SHEET_NAME", "Celestra-Output")

# Incident storage
INCIDENTS_DIR = BASE_DIR / "data" / "incidents"
os.makedirs(INCIDENTS_DIR, exist_ok=True)

#LEAKLOOKUP_API_KEY = "b7521e23e37728c234f5d642546634ea"
#LEAKLOOKUP_API_ENDPOINT = "https://leak-lookup.com/api/search"
#LEAKLOOKUP_MAX_RESULTS = 500 
HIPB_KEY = "7dc1320bc64245809b8a85643edda2b1"
IPINFO_API_KEY = "9c1b6781005624"
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", None)
if not APOLLO_API_KEY:
    raise ValueError("APOLLO_API_KEY is not set in the environment variables.")

RATE_LIMITS = {
    'apollo': 50  # or your desired rate limit value
}