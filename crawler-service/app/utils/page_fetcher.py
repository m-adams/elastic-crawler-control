"""
Page fetcher with rate limiting for site investigation.

Fetches sample pages from target sites with:
- Rate limiting (configurable delay)
- Retry logic with exponential backoff
- Bot protection detection
- Content extraction
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class FetchedPage:
    """A fetched page with metadata."""
    
    url: str
    html_content: str
    status_code: int
    content_type: Optional[str] = None
    final_url: Optional[str] = None  # After redirects
    error: Optional[str] = None


@dataclass
class PageFetchResult:
    """Result of fetching multiple pages."""
    
    pages: list[FetchedPage]
    successful: int
    failed: int
    bot_protection_detected: bool = False


class PageFetcher:
    """Fetches web pages with rate limiting and retry logic."""
    
    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        timeout: float = 30.0,
        max_retries: int = 3,
        user_agent: str = "Open-Crawler-Config-Generator/1.0 (Site Investigation Bot)",
    ):
        """
        Initialize page fetcher.
        
        Args:
            rate_limit_delay: Delay between requests in seconds
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            user_agent: User-Agent header to use
        """
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent
        self._last_request_time = 0.0
    
    async def fetch_page(self, url: str) -> FetchedPage:
        """
        Fetch a single page with retry logic.
        
        Args:
            url: URL to fetch
            
        Returns:
            Fetched page data
        """
        # Rate limiting
        await self._rate_limit()
        
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    follow_redirects=True,
                ) as client:
                    response = await client.get(url, headers=headers)
                    
                    # Check for bot protection indicators
                    if self._is_bot_protected(response):
                        return FetchedPage(
                            url=url,
                            html_content="",
                            status_code=response.status_code,
                            error="Bot protection detected (Cloudflare, Captcha, etc.)",
                        )
                    
                    response.raise_for_status()
                    
                    return FetchedPage(
                        url=url,
                        html_content=response.text,
                        status_code=response.status_code,
                        content_type=response.headers.get("content-type"),
                        final_url=str(response.url),
                    )
                    
            except httpx.HTTPError as e:
                last_error = str(e)
                
                # Exponential backoff
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                continue
        
        # All retries failed
        return FetchedPage(
            url=url,
            html_content="",
            status_code=0,
            error=f"Failed after {self.max_retries} attempts: {last_error}",
        )
    
    async def fetch_pages(self, urls: list[str]) -> PageFetchResult:
        """
        Fetch multiple pages sequentially with rate limiting.
        
        Args:
            urls: List of URLs to fetch
            
        Returns:
            Aggregate result of all fetches
        """
        pages = []
        successful = 0
        failed = 0
        bot_protection_detected = False
        
        for url in urls:
            page = await self.fetch_page(url)
            pages.append(page)
            
            if page.error:
                failed += 1
                if "bot protection" in page.error.lower():
                    bot_protection_detected = True
            else:
                successful += 1
        
        return PageFetchResult(
            pages=pages,
            successful=successful,
            failed=failed,
            bot_protection_detected=bot_protection_detected,
        )
    
    async def _rate_limit(self):
        """Apply rate limiting delay."""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - time_since_last)
        
        self._last_request_time = asyncio.get_event_loop().time()
    
    def _is_bot_protected(self, response: httpx.Response) -> bool:
        """
        Detect common bot protection mechanisms.
        
        Args:
            response: HTTP response
            
        Returns:
            True if bot protection is detected
        """
        # Check status codes
        if response.status_code in (403, 429):
            return True
        
        # Check headers
        server = response.headers.get("server", "").lower()
        if "cloudflare" in server:
            # Cloudflare challenge page
            if "cf-ray" in response.headers and len(response.text) < 10000:
                if "challenge" in response.text.lower():
                    return True
        
        # Check content
        content_lower = response.text.lower()
        bot_indicators = [
            "captcha",
            "recaptcha",
            "bot detection",
            "access denied",
            "please verify you are a human",
            "cloudflare",
            "enable javascript",
        ]
        
        for indicator in bot_indicators:
            if indicator in content_lower:
                return True
        
        return False
    
    async def sample_pages_from_sitemap(
        self,
        sitemap_urls: list[str],
        sample_size: int = 10,
        strategy: str = "distributed",
    ) -> list[str]:
        """
        Select sample page URLs from sitemap URLs.
        
        Args:
            sitemap_urls: List of URLs from sitemap
            sample_size: Number of pages to sample
            strategy: Sampling strategy ("distributed", "random", "top")
            
        Returns:
            List of sampled URLs
        """
        if len(sitemap_urls) <= sample_size:
            return sitemap_urls
        
        if strategy == "distributed":
            # Take pages evenly distributed throughout the sitemap
            step = len(sitemap_urls) / sample_size
            indices = [int(i * step) for i in range(sample_size)]
            return [sitemap_urls[i] for i in indices]
        
        elif strategy == "random":
            # Random sampling
            import random
            return random.sample(sitemap_urls, sample_size)
        
        elif strategy == "top":
            # First N pages
            return sitemap_urls[:sample_size]
        
        else:
            raise ValueError(f"Unknown sampling strategy: {strategy}")
