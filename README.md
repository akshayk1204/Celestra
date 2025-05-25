# 🌐 Celestra - Enterprise Security Enrichment & Breach Monitoring Tool

Celestra is a powerful Python-based security and intelligence tool designed to enrich domain data with CDN and WAF detection, company metadata, regional classification, and breach information from HaveIBeenPwned (HIBP). It helps security teams, analysts, and GTM teams identify target organizations with viable security postures and exposure risks.

---

## 🔧 Features

- **IP & CDN Detection**  
  Uses the IPinfo API to resolve IPs and infer associated CDN providers.

- **WAF Detection**  
  Active WAF scanning using [`wafw00f`](https://github.com/EnableSecurity/wafw00f) to identify protections like Cloudflare, Akamai, Imperva, etc.

- **Company Enrichment**  
  Integrates with Apollo API to enrich company size and metadata.

- **POC Discovery**  
  Fetches point-of-contact details for target domains (name, title, email, phone, LinkedIn).

- **Region Mapping**  
  Maps countries to high-level regions (AMER, LATAM, EMEA, APAC) via CSV.

- **HIBP Integration**  
  Checks for recent breaches via the HaveIBeenPwned v3 API.

- **Concurrency**  
  Uses `ThreadPoolExecutor` for fast parallel enrichment and scanning.

- **Google Sheets Export**  
  Supports exporting enriched data directly into a Google Sheet.

---

## 📁 Project Structure

celestra/
├── modules/
│ ├── googlesheets.py # Google Sheets export
│ └── apollo_integration.py # Apollo API wrapper
├── config/
│ ├── settings.py # API keys and constants
│ └── constants.py # Region logic
├── data/
│ ├── country_region.csv # Country-to-region mapping
│ └── last_run.txt # Timestamp tracking
├── logs/
│ └── scraper.log # Logging output
├── celestra.py # Main entry point
└── README.md # Project documentation


---

## 🛠️ Installation

### Prerequisites

- Python 3.8+
- `wafw00f` installed globally
- Google Sheets + Apollo API credentials
- IPInfo API token
- HIBP API key

### Setup

```bash
git clone https://github.com/your-org/celestra.git
cd celestra
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

🔐 Environment Configuration
Create a .env file or export the following environment variables:

export IPINFO_API_KEY="your_ipinfo_token"
export HIPB_KEY="your_hibp_api_key"
export APOLLO_API_KEY="your_apollo_token"


🚀 Usage
To run the enrichment process on a list of domains:

from celestra import filter_domains, bulk_enrich_organizations, bulk_enrich_contacts

domains = ["example.com", "company.org"]

filtered_domains = filter_domains(domains)

org_data = bulk_enrich_organizations(filtered_domains)
contacts = bulk_enrich_contacts(filtered_domains)

📊 Output
Enriched data includes:

CDN provider

WAF technology

Country + Region

Company size and name

Contact name, title, phone, email, LinkedIn

Recent breaches (via HIBP)

Output can be:

Printed to console

Saved as CSV

Exported to Google Sheets

✅ TODO / Future Improvements

Add retry + rate limit handling for Apollo and IPInfo
Improve breach filtering by domain relevance
Add CLI interface for batch usage
Support additional enrichment APIs (e.g., Crunchbase, LinkedIn)
Dockerize for containerized deployment

👨‍💻 Maintainers
Akshay Kulkarni
