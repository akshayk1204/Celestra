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


def find_similar_companies(domain: str, max_results: int = 3) -> List[Dict]:
    """Find companies in the same industry (US/CA only)"""
    try:
        # Get original company's industry first
        original = enrich_company_size(domain)
        if not original or not original.get("industry"):
            return []

        params = {
            "q_organization_industries": [original["industry"]],
            "page": 1,
            "per_page": max_results + 5,  # Over-fetch for US/CA filtering
            "organization_location_countries": ["US", "CA"],  # US/CA only
            "api_key": APOLLO_API_KEY
        }

        response = _apollo_request("GET", 
            f"{APOLLO_API_URL}/organizations/search",
            params=params
        )

        return [
            {
                "domain": org["domain"],
                "name": org["name"],
                "industry": org["industry"],
                "employees": org.get("estimated_num_employees")
            }
            for org in response.get("organizations", [])[:max_results]
            if org["domain"] != domain  # Exclude original
        ]
    except Exception as e:
        logger.error(f"Industry similarity search failed: {e}")
        return []    


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


""""
def fetch_poc_for_domain(domain: str) -> Dict[str, str]:
    
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
                "api_key": APOLLO_API_KEY,
                "reveal_personal_emails": True,  
                "reveal_phone_numbers": True 
            }

            response = _apollo_request("GET", 
                "https://api.apollo.io/v1/mixed_people/search",
                headers=headers,
                params=params
            )

            if not response or not response.get("people"):
                continue

            person = response["people"][0]
            email = person.get("email")
            if not email:
                email = person.get("personal_email", "Not Available")
            
            # Handle email restrictions
            if isinstance(email, str) and "not_unlocked" in email.lower():
                email = "Email Restricted (Upgrade Required)"

            # Get best available phone
            phone_numbers = person.get("phone_numbers", [])
            phone = phone_numbers[0].get("number") if phone_numbers else "Not Available"

            return {
                "Name": person.get("name", "Not Found"),
                "Title": title,
                "Phone": phone,
                "Email": email if email != "not_unlocked" else "Available (Upgrade Required)",
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
"""

def fetch_poc_for_domain(domain: str) -> Dict[str, str]:
    """
    Fetch point of contact using People Enrichment endpoint
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

    # Try security titles in priority order
    security_titles = [
        "Chief Information Security Officer",
        "CISO",
        "Chief Security Officer",
        "CSO",
        "VP of Security",
        "Director of Security"
    ]

    for title in security_titles:
        try:
            params = {
                "domain": domain,
                "reveal_personal_emails": True,  # Get emails
                "reveal_phone_numbers": False,    # Avoid webhook requirement
                "title": title                    # Filter by security title
            }

            response = _apollo_request(
                "POST",
                f"{APOLLO_API_URL}people/match",
                headers=headers,
                params=params
            )

            if not response or not response.get("person"):
                continue

            person = response["person"]
            
            # Email handling
            email = person.get("email")
            if not email or "not_unlocked" in str(email).lower():
                email = person.get("contact", {}).get("email", "Not Available")
            
            # Phone handling (basic - no verification)
            phone = "Not Available"
            if person.get("contact", {}).get("phone_numbers"):
                phone = person["contact"]["phone_numbers"][0].get("sanitized_number", "Not Available")

            return {
                "Name": person.get("name", "Not Found"),
                "Title": person.get("title", title),
                "Phone": phone,
                "Email": email if email != "not_unlocked" else "Available (Upgrade Required)",
                "LinkedIn URL": person.get("linkedin_url", "Not Available")
            }

        except Exception as e:
            logger.error(f"Error enriching {domain} for {title}: {str(e)}")
            continue

    # Fallback to generic lookup if no security titles found
    try:
        params = {
            "domain": domain,
            "reveal_personal_emails": True,
            "reveal_phone_numbers": False
        }

        response = _apollo_request(
            "POST",
            f"{APOLLO_API_URL}people/match",
            headers=headers,
            params=params
        )

        if response and response.get("person"):
            person = response["person"]
            email = person.get("email", "Not Available")
            phone = person.get("contact", {}).get("phone_numbers", [{}])[0].get("sanitized_number", "Not Available")
            
            return {
                "Name": person.get("name", "Not Found"),
                "Title": person.get("title", "Not Found"),
                "Phone": phone,
                "Email": email if email != "not_unlocked" else "Available (Upgrade Required)",
                "LinkedIn URL": person.get("linkedin_url", "Not Available")
            }
    except Exception as e:
        logger.error(f"Generic enrichment failed for {domain}: {str(e)}")

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
