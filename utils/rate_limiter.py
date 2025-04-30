import time
import requests
from collections import defaultdict
from config.settings import RATE_LIMITS  # Ensure this is imported from the correct config
import logging

logging.basicConfig(level=logging.WARNING)  # You can adjust the level as needed
logger = logging.getLogger(__name__)  # You can name your logger if necessary

class RateLimiter:
    def __init__(self):
        self.counts = defaultdict(int)
        self.last_reset = time.time()

    def check_limit(self, service: str) -> bool:
        """Check if the rate limit is exceeded for the given service."""
        current_time = time.time()

        # Reset count every minute
        if current_time - self.last_reset > 60:  
            self.counts.clear()
            self.last_reset = current_time

        # Check if rate limit exceeded for the service
        if self.counts[service] >= RATE_LIMITS.get(service, 10):
            time.sleep(10)  # Sleep for 10 seconds to prevent exceeding the limit
            return False
        
        self.counts[service] += 1
        return True

    def check_rate_limits(self, response_headers):
        """Check the remaining rate limit and delay if necessary."""
        remaining_requests = int(response_headers.get('x-minute-requests-left', 0))
        
        if remaining_requests < 10:  # If fewer than 10 requests left in the minute
            reset_time = int(response_headers.get('x-rate-limit-reset', time.time()))  # When limit resets
            sleep_time = reset_time - time.time() + 1  # Sleep until the reset time
            time.sleep(sleep_time)

    def enrich_website_with_apollo(self, website: str):
        """Enrich the website with Apollo data, considering rate limits."""
        if not self.check_limit('apollo'):
            return None  # If rate limit exceeded, skip request
        
        # Make the API call to Apollo
        response = requests.get(f"https://api.apollo.io/v1/people?website={website}", headers={"Authorization": "Bearer YOUR_TOKEN"})
        
        # Check and handle rate limits
        self.check_rate_limits(response.headers)

        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Failed to enrich {website} with Apollo: {response.status_code}")
            return None
