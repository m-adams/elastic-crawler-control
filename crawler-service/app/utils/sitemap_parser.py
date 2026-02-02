"""
Sitemap parser for site investigation.

Parses XML sitemaps to extract:
- URLs
- Last modification dates
- Change frequencies
- Priorities
- Nested sitemap indices
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from xml.etree import ElementTree as ET

import httpx


@dataclass
class SitemapURL:
    """A single URL entry from a sitemap."""
    
    loc: str
    lastmod: Optional[datetime] = None
    changefreq: Optional[str] = None
    priority: Optional[float] = None


@dataclass
class SitemapData:
    """Parsed sitemap data."""
    
    sitemap_url: str
    urls: list[SitemapURL]
    nested_sitemaps: list[str]
    accessible: bool = True
    error: Optional[str] = None


class SitemapParser:
    """Parser for XML sitemaps."""
    
    # XML namespaces
    NS = {
        "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    }
    
    def __init__(self, timeout: float = 30.0, max_urls: int = 1000):
        """
        Initialize sitemap parser.
        
        Args:
            timeout: Request timeout in seconds
            max_urls: Maximum number of URLs to extract per sitemap
        """
        self.timeout = timeout
        self.max_urls = max_urls
    
    async def fetch_and_parse(self, sitemap_url: str) -> SitemapData:
        """
        Fetch and parse a sitemap.
        
        Args:
            sitemap_url: URL of the sitemap
            
        Returns:
            Parsed sitemap data
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    sitemap_url,
                    follow_redirects=True,
                    headers={"User-Agent": "Open-Crawler-Config-Generator/1.0"},
                )
                response.raise_for_status()
                content = response.content
                
        except httpx.HTTPError as e:
            return SitemapData(
                sitemap_url=sitemap_url,
                urls=[],
                nested_sitemaps=[],
                accessible=False,
                error=f"Failed to fetch sitemap: {str(e)}",
            )
        
        # Parse XML
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            return SitemapData(
                sitemap_url=sitemap_url,
                urls=[],
                nested_sitemaps=[],
                accessible=False,
                error=f"Failed to parse sitemap XML: {str(e)}",
            )
        
        # Determine sitemap type
        if self._is_sitemap_index(root):
            return self._parse_sitemap_index(sitemap_url, root)
        else:
            return self._parse_urlset(sitemap_url, root)
    
    def _is_sitemap_index(self, root: ET.Element) -> bool:
        """
        Check if this is a sitemap index (contains nested sitemaps).
        
        Args:
            root: XML root element
            
        Returns:
            True if this is a sitemap index
        """
        # Check for sitemapindex tag
        if "sitemapindex" in root.tag.lower():
            return True
        
        # Check for sitemap children
        sitemaps = root.findall(".//sm:sitemap", self.NS)
        if not sitemaps:
            # Try without namespace
            sitemaps = root.findall(".//sitemap")
        
        return len(sitemaps) > 0
    
    def _parse_sitemap_index(self, sitemap_url: str, root: ET.Element) -> SitemapData:
        """
        Parse a sitemap index (list of sitemaps).
        
        Args:
            sitemap_url: URL of the sitemap index
            root: XML root element
            
        Returns:
            Parsed sitemap data with nested sitemaps
        """
        nested_sitemaps = []
        
        # Try with namespace
        sitemaps = root.findall(".//sm:sitemap", self.NS)
        if not sitemaps:
            # Try without namespace
            sitemaps = root.findall(".//sitemap")
        
        for sitemap in sitemaps:
            loc = sitemap.find("sm:loc", self.NS)
            if loc is None:
                loc = sitemap.find("loc")
            
            if loc is not None and loc.text:
                nested_sitemaps.append(loc.text.strip())
        
        return SitemapData(
            sitemap_url=sitemap_url,
            urls=[],
            nested_sitemaps=nested_sitemaps,
            accessible=True,
        )
    
    def _parse_urlset(self, sitemap_url: str, root: ET.Element) -> SitemapData:
        """
        Parse a URL set sitemap.
        
        Args:
            sitemap_url: URL of the sitemap
            root: XML root element
            
        Returns:
            Parsed sitemap data with URLs
        """
        urls = []
        
        # Try with namespace
        url_elements = root.findall(".//sm:url", self.NS)
        if not url_elements:
            # Try without namespace
            url_elements = root.findall(".//url")
        
        for url_elem in url_elements[:self.max_urls]:
            loc = self._get_text(url_elem, "loc")
            if not loc:
                continue
            
            lastmod_str = self._get_text(url_elem, "lastmod")
            lastmod = self._parse_datetime(lastmod_str) if lastmod_str else None
            
            changefreq = self._get_text(url_elem, "changefreq")
            
            priority_str = self._get_text(url_elem, "priority")
            priority = None
            if priority_str:
                try:
                    priority = float(priority_str)
                except ValueError:
                    pass
            
            urls.append(SitemapURL(
                loc=loc,
                lastmod=lastmod,
                changefreq=changefreq,
                priority=priority,
            ))
        
        return SitemapData(
            sitemap_url=sitemap_url,
            urls=urls,
            nested_sitemaps=[],
            accessible=True,
        )
    
    def _get_text(self, element: ET.Element, tag: str) -> Optional[str]:
        """
        Get text content of a child element.
        
        Args:
            element: Parent element
            tag: Child tag name
            
        Returns:
            Text content or None
        """
        # Try with namespace
        child = element.find(f"sm:{tag}", self.NS)
        if child is None:
            # Try without namespace
            child = element.find(tag)
        
        if child is not None and child.text:
            return child.text.strip()
        
        return None
    
    def _parse_datetime(self, date_str: str) -> Optional[datetime]:
        """
        Parse ISO 8601 datetime string.
        
        Args:
            date_str: ISO 8601 datetime string
            
        Returns:
            Parsed datetime or None
        """
        # Common formats in sitemaps
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S.%f%z",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        return None
    
    async def fetch_all_urls(
        self,
        sitemap_urls: list[str],
        max_depth: int = 2,
    ) -> list[SitemapURL]:
        """
        Fetch and parse multiple sitemaps, following nested sitemaps.
        
        Args:
            sitemap_urls: List of sitemap URLs to parse
            max_depth: Maximum depth for following nested sitemaps
            
        Returns:
            Aggregated list of URLs from all sitemaps
        """
        all_urls = []
        visited = set()
        
        async def process_sitemap(url: str, depth: int):
            if depth > max_depth or url in visited:
                return
            
            visited.add(url)
            data = await self.fetch_and_parse(url)
            
            if not data.accessible:
                return
            
            # Add URLs from this sitemap
            all_urls.extend(data.urls)
            
            # Recursively process nested sitemaps
            if depth < max_depth:
                for nested_url in data.nested_sitemaps:
                    await process_sitemap(nested_url, depth + 1)
        
        # Process all provided sitemaps
        for url in sitemap_urls:
            await process_sitemap(url, 0)
        
        return all_urls
