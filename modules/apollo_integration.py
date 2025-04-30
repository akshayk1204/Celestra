import sys
import os
import logging
import time
import requests
from config.settings import APOLLO_API_KEY
from utils.rate_limiter import RateLimiter
from typing import List, Dict, Tuple, Optional
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize rate limiter
rate_limiter = RateLimiter()

# Constants
APOLLO_API_URL = 'https://api.apollo.io/api/v1/'
MAX_RETRIES = 5
RETRY_BACKOFF = 2

# Caches
company_cache = {}

# Session setup
session = requests.Session()
session.headers.update({
    "x-api-key": APOLLO_API_KEY,
    "accept": "application/json",
    "Content-Type": "application/json",
    "Cache-Control": "no-cache"
})
# Helper to send requests with retry + rate limit handling
def _apollo_request(method, url, json=None, params=None, headers=None):
    print(f"✅ Making Apollo request to {url}")

    for attempt in range(MAX_RETRIES):
        if not rate_limiter.check_limit('apollo'):
            logger.info("Rate limit exceeded for Apollo. Skipping request.")
            return None
        try:
            logger.info(f"➡️  Sending request to Apollo: {method} {url}")
            if params:
                logger.info(f"➡️  Params: {params}")
            if json:
                logger.info(f"➡️  Payload: {json}")

            response = session.request(method, url, json=json, params=params, headers=headers, timeout=10)

            logger.info(f"⬅️  Status Code: {response.status_code}")
            logger.info(f"⬅️  Headers: {response.headers}")
            logger.info(f"⬅️  Raw Content: {response.text}")

            if response.status_code == 429:
                wait_time = RETRY_BACKOFF ** attempt
                logger.warning(f"Rate limit hit. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            elif response.status_code == 401:
                logger.error("❌ Authentication error. Check API Key.")
                return None
            elif response.status_code == 422:
                logger.error("❌ Unprocessable Entity (422). Check if the domain is valid.")
                return None

            rate_limiter.check_rate_limits(response.headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"❌ Apollo API error: {e}")
            time.sleep(RETRY_BACKOFF ** attempt)
    logger.error(f"❌ Failed after {MAX_RETRIES} attempts: {url}")
    return None

def find_similar_companies(domain: str, regions: list = ["AMER"], min_employees: int = 50) -> List[Dict]:
    """Find similar companies based on original company's attributes"""
    if not domain:
        return []
    
    # First get the original company's data
    original = enrich_company_size(domain)
    if not original or original.get("Company Size") == "N/A":
        return []
    
    similar_companies = []
    url = f"{APOLLO_API_URL}/mixed_people/search"
    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "x-api-key": APOLLO_API_KEY
    }
    
    params = {
        "q_organization_domains": domain,
        "page": 1,
        "per_page": 10,  # Get top 10 similar
        "organization_num_employees_ranges": original.get("estimated_num_employees_range", "50-1000"),
        "api_key": APOLLO_API_KEY
    }
    
    response = _apollo_request("GET", url, headers=headers, params=params)
    
    if response and response.get("organizations"):
        for org in response["organizations"]:
            if org["domain"] != domain:  # Exclude original
                similar_companies.append({
                    "domain": org["domain"],
                    "name": org["name"],
                    "estimated_num_employees": org.get("estimated_num_employees"),
                    "industry": org.get("industry")
                })
    
    return similar_companies

# Main enrichment function for Company Size only
def enrich_company_size(domain: str) -> Dict[str, str]:
    if domain in company_cache:
        return company_cache[domain]

    url = f"https://api.apollo.io/api/v1/organizations/enrich?domain={domain}"
    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "accept": "application/json",
        "x-api-key": APOLLO_API_KEY
    }

    data = _apollo_request("GET", url, headers=headers)

    if not data or not data.get("organization"):
        logger.warning(f"No company data found for domain: {domain}")
        company_cache[domain] = {
            "Company Size": "N/A",
            "Company Name": "Unknown"
        }
        return company_cache[domain]

    company = data["organization"]
    size = company.get("estimated_num_employees")
    name = company.get("name", "Unknown")

    if size is None:
        size_bucket = "N/A"
    elif size < 50:
        size_bucket = "1–49"
    elif size < 250:
        size_bucket = "50–249"
    elif size < 1000:
        size_bucket = "250–999"
    elif size < 5000:
        size_bucket = "1,000–4,999"
    else:
        size_bucket = "5,000+"

    enriched = {
        "Company Size": size_bucket,
        "Company Name": name
    }
    company_cache[domain] = enriched
    return enriched



def fetch_poc_for_domain(domain: str) -> Dict[str, str]:
    """
    Enhanced contact lookup with better error handling and LinkedIn support
    Returns: {
        "Name": str,
        "Title": str,
        "Phone": str,
        "Email": str,
        "LinkedIn URL": str
    }
    """
    if not domain:
        return {
            "Name": "Not Found",
            "Title": "Not Found",
            "Phone": "Not Available",
            "Email": "Not Available",
            "LinkedIn URL": "Not Available"
        }

    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "x-api-key": APOLLO_API_KEY
    }

    # Expanded title search list with priority order
    security_titles = [
        "Chief Information Security Officer",
        "CISO",
        "Chief Security Officer",
        "CSO",
        "VP of Security",
        "Vice President of Security",
        "Director of Security",
        "Head of Security",
        "Security Manager",
        "IT Security Manager",
        "Information Security Manager"
    ]

    for title in security_titles:
        try:
            params = {
                "q_organization_domains": domain,
                "q_titles": [title],
                "page": 1,
                "per_page": 1,
                "api_key": APOLLO_API_KEY
            }

            response = _apollo_request("GET", 
                "https://api.apollo.io/v1/mixed_people/search",
                headers=headers,
                params=params
            )

            if not response or not response.get("people"):
                continue

            person = response["people"][0]
            email = person.get("email", "Not Available")
            
            # Handle email restrictions
            if isinstance(email, str) and "not_unlocked" in email.lower():
                email = "Email Restricted (Upgrade Required)"

            return {
                "Name": person.get("name", "Not Found"),
                "Title": title,
                "Phone": person.get("phone_numbers", [{}])[0].get("number", "Not Available"),
                "Email": email,
                "LinkedIn URL": person.get("linkedin_url", "Not Available")
            }

        except Exception as e:
            logger.error(f"Error searching {domain} for {title}: {str(e)}")
            continue

    return {
        "Name": "Not Found",
        "Title": "Not Found",
        "Phone": "Not Available",
        "Email": "Not Available",
        "LinkedIn URL": "Not Available"
    }

    

# Example CLI usage
if __name__ == "__main__":
    import json

    test_domain = sys.argv[1] if len(sys.argv) > 1 else "cloudflare.com"
    logger.info(f"Testing Apollo enrichment for: {test_domain}")

    result = enrich_company_size(test_domain)

    print("\n✅ Enriched Company Info:")
    print(json.dumps(result, indent=2))
