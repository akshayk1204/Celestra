import requests
import yaml
import concurrent.futures
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from config.settings import HIPB_KEY
from pathlib import Path
import sys
import os
import logging
import subprocess
import time
import socket
import re
import csv
from modules.googlesheets import GoogleSheetsExporter
from modules.apollo_integration import enrich_company_size, fetch_poc_for_domain,find_similar_companies
from config.constants import INCLUDED_REGIONS
from pathlib import Path


# Ensure logs/ directory exists
Path("logs").mkdir(exist_ok=True)

# Set up file and console handlers explicitly
logger = logging.getLogger()  # root logger
logger.setLevel(logging.INFO)

# Clear existing handlers (important if running in notebooks or scripts)
logger.handlers.clear()

file_handler = logging.FileHandler("logs/scraper.log")
console_handler = logging.StreamHandler()

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
#logger.addHandler(console_handler)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add modules path
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
IPINFO_API_KEY = os.getenv("IPINFO_API_KEY")

# Configure requests session
session = requests.Session()
session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
session.headers.update({
    "hibp-api-key": HIPB_KEY,
    "user-agent": "CelestraBreachMonitor/1.0"
})


# Global constants
DATA_DIR = Path("data")
LAST_RUN_FILE = DATA_DIR / "last_run.txt"
WAF_TIMEOUT = 20  # seconds
MAX_WORKERS = 10  # concurrency level

# Load country-region mapping once
country_region_map = {}


def is_valid_website(website: str) -> bool:
    if not website:
        return False
    website = website.replace('http://', '').replace('https://', '').split('/')[0]
    try:
        socket.gethostbyname(website)
        return True
    except socket.error:
        return False


def load_country_region_mapping(file_path: str) -> Dict[str, str]:
    region_mapping = {}
    with open(file_path, mode='r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            country_code = row['alpha-2']
            region = row['region']
            # Update region handling
            if region == 'Americas':
                if country_code in ['US', 'CA']:  # These should remain AMER
                    region_abbr = 'AMER'
                else:  # Everything else in Americas is LATAM
                    region_abbr = 'LATAM'
            elif region == 'Europe':
                region_abbr = 'EMEA'
            elif region == 'Asia':
                region_abbr = 'APAC'
            elif region == 'Africa':
                region_abbr = 'EMEA'
            elif region == 'Oceania':
                region_abbr = 'APAC'
            else:
                region_abbr = 'Unknown'
            region_mapping[country_code] = region_abbr
    return region_mapping


# Load on start
country_region_map = load_country_region_mapping('data/country_region.csv')


def get_ipinfo(website: str) -> Tuple[str, str]:
    try:
        ip = socket.gethostbyname(website)
        response = requests.get(f"https://ipinfo.io/{ip}/json?token={IPINFO_API_KEY}", timeout=8)
        response.raise_for_status()
        data = response.json()

        cdn = re.sub(r"AS\d+\s*", "", data.get('org', '')).strip() if 'org' in data else "None"
        country = data.get('country', 'Unknown')
        return cdn, country

    except Exception as e:
        logger.warning(f"[IPInfo Error] {website}: {e}")
        return "None", "Unknown"


def detect_waf(website: str) -> str:
    try:
        waf_output = subprocess.check_output(["wafw00f", website], stderr=subprocess.DEVNULL, timeout=WAF_TIMEOUT).decode("utf-8")
        waf_keywords = [
            "Cloudflare", "Akamai", "Fastly", "AWS", "Amazon", "Google", "Azure",
            "Imperva", "F5", "Radware", "Edgecast", "Sucuri", "Wordfence",
            "StackPath", "SiteLock", "Barracuda", "Fortinet", "DenyALL", "DDoS-GUARD"
        ]
        found_wafs = [waf for waf in waf_keywords if waf.lower() in waf_output.lower()]
        return ", ".join(sorted(set(found_wafs))) if found_wafs else "None"
    except subprocess.TimeoutExpired:
        logger.warning(f"[WAF Timeout] {website}")
        return "Timeout"
    except subprocess.CalledProcessError:
        logger.warning(f"[WAF Error] {website}")
        return "None"

def filter_domains(domains: List[str]) -> List[str]:
    """Filter domains based on company size and region"""
    filtered = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_domain = {executor.submit(enrich_company_size, domain): domain for domain in domains}
        
        for future in concurrent.futures.as_completed(future_to_domain):
            domain = future_to_domain[future]
            try:
                result = future.result()
                company_size = result.get("Company Size", "N/A")
                
                # Skip if company size is unknown or too small
                if company_size in ["N/A", "1–49"]:
                    continue
                    
                filtered.append(domain)
            except Exception as e:
                logger.error(f"Error filtering domain {domain}: {e}")
    
    return filtered

def bulk_enrich_organizations(domains: List[str]) -> Dict[str, Dict]:
    """Bulk enrich organization data"""
    enriched = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_domain = {executor.submit(enrich_website, domain): domain for domain in domains}
        
        for future in concurrent.futures.as_completed(future_to_domain):
            domain = future_to_domain[future]
            try:
                cdn, security, country, company_size, company_name = future.result()
                enriched[domain] = {
                    "CDN": cdn,
                    "Security": security,
                    "Country": country,
                    "Company Size": company_size,
                    "Company Name": company_name
                }
            except Exception as e:
                logger.error(f"Error enriching organization {domain}: {e}")
                enriched[domain] = {
                    "CDN": "None",
                    "Security": "None",
                    "Country": "Unknown",
                    "Company Size": "N/A",
                    "Company Name": "Unknown"
                }
    
    return enriched

def bulk_enrich_contacts(domains: List[str]) -> Dict[str, Dict]:
    """Bulk enrich contact information"""
    contacts = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_domain = {executor.submit(fetch_poc_for_domain, domain): domain for domain in domains}
        
        for future in concurrent.futures.as_completed(future_to_domain):
            domain = future_to_domain[future]
            try:
                contact_data = future.result()
                contacts[domain] = {
                    "Contact Name": contact_data.get("Name", "Not Found"),
                    "Contact Title": contact_data.get("Title", "Not Found"),
                    "Contact Phone": contact_data.get("Phone", "Not Found"),
                    "Contact Email": contact_data.get("Email", "Not Found"),
                    "LinkedIn URL": contact_data.get("LinkedIn URL", "Not Available")
                }
            except Exception as e:
                logger.error(f"Error enriching contacts for {domain}: {e}")
                contacts[domain] = {
                    "Contact Name": "Not Found",
                    "Contact Title": "Not Found",
                    "Contact Phone": "Not Available",
                    "Contact Email": "Not Available",
                    "LinkedIn URL": "Not Available"
                }
    
    return contacts


def enrich_website(website: str) -> Tuple[str, str, str, str, str]:
    website = website.replace('http://', '').replace('https://', '').split('/')[0]
    cdn, country = get_ipinfo(website)
    security = detect_waf(website)
    region = country_region_map.get(country, 'Unknown')

    # AMER for US and CA, LATAM for everything else in the Americas
    if region == 'LATAM':
        region = 'LATAM'
    elif region == 'AMER':
        region = 'AMER'

    country_with_region = f"{country}-{region}" if region != 'Unknown' else country

    # Get company data
    try:
        domain = website
        company_data = enrich_company_size(domain)
        company_size = company_data.get("Company Size", "Unknown")
        company_name = company_data.get("Company Name", "Unknown")
    except Exception as e:
        logger.warning(f"Error fetching company data for {domain}: {e}")
        company_size = "Unknown"
        company_name = "Unknown"

    logger.info(f"Apollo enriched data for {website}: {company_name} ({company_size})")
    return cdn, security, country_with_region, company_size, company_name


def fetch_hipb_breaches() -> List[Dict]:
    try:
        logger.info("Fetching breaches from HIBP...")
        url = "https://haveibeenpwned.com/api/v3/breaches"
        response = session.get(url)
        response.raise_for_status()
        breaches = response.json()

        incidents = []
        for b in breaches:
            breach_year = datetime.strptime(b["AddedDate"], "%Y-%m-%dT%H:%M:%SZ").year
            if breach_year >= datetime.now().year - 1:  # Current and previous year
                incidents.append({
                    "date": b["BreachDate"],
                    "source": "HIBP",
                    "source_url": f"https://haveibeenpwned.com/PwnedWebsites#{b['Name']}",
                    "raw_content": ", ".join(b.get("DataClasses", [])),
                    "organizations": [b["Domain"]] if b.get("Domain") else []
                })

        logger.info(f"Fetched {len(incidents)} breaches from HIBP.")
        return incidents
    except Exception as e:
        logger.error(f"Error fetching breaches from HIBP: {str(e)}")
        return []


def deduplicate_incidents(incidents: List[Dict]) -> List[Dict]:
    seen = set()
    deduped = []
    for incident in incidents:
        orgs = incident.get('organizations', [])
        domain = orgs[0] if orgs else None
        key = (incident.get('title'), domain)
        if key not in seen:
            seen.add(key)
            deduped.append(incident)
    return deduped


def load_sources():
    try:
        with open('config/sources.yaml', 'r') as f:
            sources = yaml.safe_load(f)
        logger.info("Successfully loaded sources configuration.")
        return sources
    except Exception as e:
        logger.error(f"Failed to load sources.yaml: {str(e)}")
        return {}


def load_last_run() -> str:
    try:
        with open(LAST_RUN_FILE, 'r') as f:
            last_run_date = f.read().strip()
        logger.info(f"Loaded last run date: {last_run_date}")
        return last_run_date
    except FileNotFoundError:
        logger.warning("Last run file not found. Starting fresh.")
        return None


def save_last_run(date_str: str):
    DATA_DIR.mkdir(exist_ok=True)
    with open(LAST_RUN_FILE, 'w') as f:
        f.write(date_str)
    logger.info(f"Saved last run date: {date_str}")


def normalize_domain(url: str) -> str:
    return url.replace('http://', '').replace('https://', '').split('/')[0].lower()

def flatten_incident_data(incident: Dict, enrich: bool = True) -> Dict:
    key_mapping = {
        "date": "Date of Breach",
        "source": "Source",
        "raw_content": "Type of Breach",
        "organizations": "Company Website"
    }

    flattened = {}
    
    # Handle organizations field
    orgs = incident.get("organizations")
    if orgs is not None:
        if isinstance(orgs, list):
            flattened["Company Website"] = orgs[0] if orgs else ""
        else:
            flattened["Company Website"] = str(orgs)
    else:
        flattened["Company Website"] = ""

    # Map other fields (excluding 'title' which was for Breach)
    for old_key, new_key in key_mapping.items():
        if old_key in incident and old_key != "organizations":
            flattened[new_key] = incident[old_key]

    # Set default values
    defaults = {
        "CDN": "None",
        "Security": "None",
        "Country": "Unknown",
        "Company Size": "N/A",
        "Company Name": "Unknown",
        "Contact Name": "Not Found",
        "Contact Title": "Not Found",
        "Contact Phone": "Not Found",
        "Contact Email": "Not Found",
        "LinkedIn URL": "Not Available"
    }
    
    for key, value in defaults.items():
        if key not in flattened:
            flattened[key] = value

    # Skip if no website
    if not flattened.get("Company Website"):
        return None

    if enrich and flattened.get("Company Website"):
        website = flattened["Company Website"]
        try:
            cdn, security, country, company_size, company_name = enrich_website(website)
            flattened.update({
                "CDN": cdn,
                "Security": security,
                "Country": country,
                "Company Size": company_size,
                "Company Name": company_name
            })
        except Exception as e:
            logger.error(f"Enrichment failed for {website}: {e}")

    return flattened

def scrape_security_incidents(last_run_date: str = None) -> Tuple[List[Dict], str]:
    """Main function implementing the new flow"""
    # Step 1: Fetch breaches
    incidents = fetch_hipb_breaches()
    incidents = deduplicate_incidents(incidents)
    
    # Filter by date if needed
    if last_run_date:
        try:
            last_date = datetime.strptime(last_run_date, '%Y-%m-%d')
            incidents = [i for i in incidents if datetime.strptime(i['date'], '%Y-%m-%d') > last_date]
        except ValueError:
            logger.error(f"Invalid last run date format: {last_run_date}")

    # Step 2: Extract domains
    domains = []
    incident_map = {}
    for incident in incidents:
        flat = flatten_incident_data(incident, enrich=False)
        if flat and flat.get("Company Website"):
            domain = normalize_domain(flat["Company Website"].split(",")[0])
            if is_valid_website(domain):
                domains.append(domain)
                incident_map[domain] = flat

    # Step 3: Filter by size/region
    filtered_domains = filter_domains(domains)
    
    # Step 4: Bulk enrich organizations
    org_data = bulk_enrich_organizations(filtered_domains)
    
    # Step 5: Bulk enrich contacts
    contact_data = bulk_enrich_contacts(filtered_domains)
    
    # Combine all data
    flattened = []
    seen_domains = set()  # To avoid duplicates
    
    for domain in filtered_domains:
        if domain in incident_map and domain not in seen_domains:
            incident = incident_map[domain]
            incident.update(org_data.get(domain, {}))
            incident.update(contact_data.get(domain, {}))
            
            # Region filtering
            country = incident.get("Country", "")
            if not (country.startswith("US-") or country.startswith("CA-")):
                continue
                
            flattened.append(incident)
            seen_domains.add(domain)
            
            # NEW: Find similar companies
            similar = find_similar_companies(domain)
            for company in similar:
                if company["domain"] not in seen_domains:
                    similar_incident = {
                        "Date of Breach": "Similar Company",
                        "Source": "Apollo",
                        "Type of Breach": "Potential Target",
                        "Company Website": company["domain"],
                        "Company Name": company["name"],
                        "Company Size": company.get("estimated_num_employees", "N/A"),
                        "Industry": company.get("industry", "")
                    }
                    
                    # Enrich the similar company
                    try:
                        cdn, security, country, size, name = enrich_website(company["domain"])
                        similar_incident.update({
                            "CDN": cdn,
                            "Security": security,
                            "Country": country
                        })
                        flattened.append(similar_incident)
                        seen_domains.add(company["domain"])
                    except Exception as e:
                        logger.error(f"Failed to enrich similar company {company['domain']}: {e}")
    
    logger.info(f"Processed {len(flattened)} incidents (original + similar).")
    return flattened, datetime.now().strftime('%Y-%m-%d')

def print_simple_breaches(incidents: List[Dict]):
    print("\nBreaches:\n")
    print(f"{'Date':<12} | {'Domain':<30} | {'Company':<25} | {'Name':<25} | {'Source':<10} | {'Size':<12} | Compromised Data")
    print("-" * 145)
    for incident in incidents:
        date = incident.get('Date of Breach', 'N/A')
        domain = incident.get('Company Website', 'N/A')
        breach = incident.get('Breach', 'N/A')
        name = incident.get('Company Name', 'N/A')
        source = incident.get('Source', 'N/A')
        company_size = incident.get('Company Size', 'N/A')
        data = incident.get('Type of Breach', 'N/A')
        
        print(f"{date:<12} | {domain:<30} | {breach:<25} | {name:<25} | {source:<10} | {company_size:<12} | {data}")


if __name__ == "__main__":
    last_run = load_last_run()
    incidents, now = scrape_security_incidents(last_run)

    #print_simple_breaches(incidents)

    exporter = GoogleSheetsExporter()
    success = exporter.export_incidents(incidents)

    if success:
        print("Incidents successfully exported to Google Sheets!")
        save_last_run(now)
    else:
        print("Failed to export incidents.")
