"""
Base scraper class with rate limiting and retry logic.
"""
import time
import logging
from abc import ABC, abstractmethod

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import settings

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for all scrapers with common HTTP handling."""
    
    def __init__(self, rate_limit: float = 1.0):
        self.rate_limit = rate_limit
        self.last_request_time = 0.0
        self.client = httpx.Client(
            timeout=settings.REQUEST_TIMEOUT,
            headers=settings.HEADERS,
            follow_redirects=True,
        )
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()
    
    def _rate_limit_wait(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        wait_time = (1.0 / self.rate_limit) - elapsed
        if wait_time > 0:
            time.sleep(wait_time)
        self.last_request_time = time.time()
    
    @retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.RETRY_BACKOFF, min=1, max=30),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
    )
    def _fetch(self, url: str, **kwargs) -> httpx.Response:
        """Fetch URL with rate limiting and retries."""
        self._rate_limit_wait()
        logger.debug(f"Fetching: {url}")
        
        response = self.client.get(url, **kwargs)
        
        # Handle rate limiting responses
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            logger.warning(f"Rate limited. Waiting {retry_after}s")
            time.sleep(retry_after)
            raise httpx.HTTPStatusError(
                f"Rate limited",
                request=response.request,
                response=response,
            )
        
        response.raise_for_status()
        return response
    
    def fetch_json(self, url: str, **kwargs) -> dict:
        """Fetch and parse JSON response."""
        response = self._fetch(url, **kwargs)
        return response.json()
    
    def fetch_binary(self, url: str, **kwargs) -> bytes:
        """Fetch binary content (PDFs, images)."""
        response = self._fetch(url, **kwargs)
        return response.content
    
    @abstractmethod
    def scrape(self, *args, **kwargs):
        """Main scraping method - implement in subclasses."""
        pass
