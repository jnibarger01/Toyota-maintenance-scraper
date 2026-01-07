"""
HTTP fetcher with rate limiting, retries, and error handling.
"""
import time
import random
import logging
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Result of a fetch operation."""
    success: bool
    url: str
    status_code: Optional[int] = None
    content: Optional[bytes] = None
    text: Optional[str] = None
    json_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    content_type: Optional[str] = None


class Fetcher:
    """
    HTTP client with rate limiting and retries.
    
    Features:
    - Configurable rate limiting with jitter
    - Exponential backoff on retries
    - Proper timeout handling
    - User-agent rotation (minimal set)
    """
    
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    def __init__(
        self,
        rate_limit: float = 1.0,
        timeout: int = 30,
        max_retries: int = 3,
        jitter: float = 0.3,
    ):
        """
        Initialize fetcher.
        
        Args:
            rate_limit: Minimum seconds between requests
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            jitter: Random jitter factor (0-1) added to rate limit
        """
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.max_retries = max_retries
        self.jitter = jitter
        self._last_request_time: Dict[str, float] = {}  # Per-domain tracking
        
        self.client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers=self.DEFAULT_HEADERS,
        )
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL for per-domain rate limiting."""
        return urlparse(url).netloc
    
    def _wait_for_rate_limit(self, domain: str) -> None:
        """Wait if needed to respect rate limit for domain."""
        if domain in self._last_request_time:
            elapsed = time.time() - self._last_request_time[domain]
            wait_time = self.rate_limit + random.uniform(0, self.rate_limit * self.jitter)
            if elapsed < wait_time:
                sleep_time = wait_time - elapsed
                logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s for {domain}")
                time.sleep(sleep_time)
        self._last_request_time[domain] = time.time()
    
    def fetch(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        as_json: bool = False,
    ) -> FetchResult:
        """
        Fetch URL with retries and rate limiting.
        
        Args:
            url: URL to fetch
            headers: Additional headers
            params: Query parameters
            as_json: Parse response as JSON
            
        Returns:
            FetchResult with success status and content
        """
        domain = self._get_domain(url)
        merged_headers = {**self.DEFAULT_HEADERS, **(headers or {})}
        
        for attempt in range(self.max_retries):
            self._wait_for_rate_limit(domain)
            
            try:
                logger.info(f"Fetching: {url} (attempt {attempt + 1}/{self.max_retries})")
                response = self.client.get(url, headers=merged_headers, params=params)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limited, waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue
                
                # Handle server errors with retry
                if response.status_code >= 500:
                    backoff = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Server error {response.status_code}, retrying in {backoff:.1f}s")
                    time.sleep(backoff)
                    continue
                
                # Build result
                content_type = response.headers.get("content-type", "")
                result = FetchResult(
                    success=response.status_code == 200,
                    url=url,
                    status_code=response.status_code,
                    content=response.content,
                    content_type=content_type,
                )
                
                if response.status_code == 200:
                    if as_json or "application/json" in content_type:
                        try:
                            result.json_data = response.json()
                        except Exception as e:
                            logger.warning(f"Failed to parse JSON: {e}")
                            result.text = response.text
                    elif "text" in content_type or "xml" in content_type:
                        result.text = response.text
                
                return result
                
            except httpx.TimeoutException:
                logger.warning(f"Timeout fetching {url}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return FetchResult(success=False, url=url, error="Timeout")
                
            except httpx.RequestError as e:
                logger.warning(f"Request error: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return FetchResult(success=False, url=url, error=str(e))
        
        return FetchResult(success=False, url=url, error="Max retries exceeded")
    
    def fetch_pdf(self, url: str) -> FetchResult:
        """Fetch PDF file."""
        return self.fetch(url, headers={"Accept": "application/pdf"})
    
    def fetch_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> FetchResult:
        """Fetch JSON API response."""
        return self.fetch(
            url,
            headers={"Accept": "application/json"},
            params=params,
            as_json=True,
        )
    
    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()
    
    def __enter__(self) -> "Fetcher":
        return self
    
    def __exit__(self, *args) -> None:
        self.close()
