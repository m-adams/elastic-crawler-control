"""
Robots.txt parser for site investigation.

Parses robots.txt files to extract:
- Crawl rules (User-agent directives, Allow/Disallow patterns)
- Sitemap URLs
- Crawl-delay directives
"""

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx


@dataclass
class RobotsRule:
    """A single rule from robots.txt."""
    
    user_agent: str
    allow: list[str]
    disallow: list[str]
    crawl_delay: Optional[float] = None


@dataclass
class RobotsData:
    """Parsed robots.txt data."""
    
    raw_content: str
    rules: list[RobotsRule]
    sitemaps: list[str]
    accessible: bool = True
    error: Optional[str] = None


class RobotsParser:
    """Parser for robots.txt files."""
    
    def __init__(self, timeout: float = 10.0):
        """
        Initialize robots.txt parser.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
    
    async def fetch_and_parse(self, domain: str) -> RobotsData:
        """
        Fetch and parse robots.txt from a domain.
        
        Args:
            domain: Domain URL (e.g., "https://example.com")
            
        Returns:
            Parsed robots.txt data
        """
        # Normalize domain
        if not domain.startswith(("http://", "https://")):
            domain = f"https://{domain}"
        
        # Construct robots.txt URL
        robots_url = urljoin(domain, "/robots.txt")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    robots_url,
                    follow_redirects=True,
                    headers={"User-Agent": "Open-Crawler-Config-Generator/1.0"},
                )
                
                if response.status_code == 404:
                    # No robots.txt - everything is allowed
                    return RobotsData(
                        raw_content="",
                        rules=[],
                        sitemaps=[],
                        accessible=True,
                    )
                
                response.raise_for_status()
                content = response.text
                
        except httpx.HTTPError as e:
            return RobotsData(
                raw_content="",
                rules=[],
                sitemaps=[],
                accessible=False,
                error=f"Failed to fetch robots.txt: {str(e)}",
            )
        
        # Parse the content
        rules = self._parse_rules(content)
        sitemaps = self._extract_sitemaps(content)
        
        return RobotsData(
            raw_content=content,
            rules=rules,
            sitemaps=sitemaps,
            accessible=True,
        )
    
    def _parse_rules(self, content: str) -> list[RobotsRule]:
        """
        Parse robots.txt content into rules.
        
        Args:
            content: Raw robots.txt content
            
        Returns:
            List of parsed rules
        """
        rules = []
        current_user_agent = None
        current_allow = []
        current_disallow = []
        current_crawl_delay = None
        
        for line in content.split("\n"):
            # Remove comments and whitespace
            line = line.split("#")[0].strip()
            if not line:
                continue
            
            # Parse directive
            if ":" not in line:
                continue
            
            directive, value = line.split(":", 1)
            directive = directive.strip().lower()
            value = value.strip()
            
            if directive == "user-agent":
                # Save previous rule if exists
                if current_user_agent is not None:
                    rules.append(RobotsRule(
                        user_agent=current_user_agent,
                        allow=current_allow,
                        disallow=current_disallow,
                        crawl_delay=current_crawl_delay,
                    ))
                
                # Start new rule
                current_user_agent = value
                current_allow = []
                current_disallow = []
                current_crawl_delay = None
                
            elif directive == "allow":
                if current_user_agent is not None:
                    current_allow.append(value)
                    
            elif directive == "disallow":
                if current_user_agent is not None:
                    current_disallow.append(value)
                    
            elif directive == "crawl-delay":
                if current_user_agent is not None:
                    try:
                        current_crawl_delay = float(value)
                    except ValueError:
                        pass
        
        # Save last rule
        if current_user_agent is not None:
            rules.append(RobotsRule(
                user_agent=current_user_agent,
                allow=current_allow,
                disallow=current_disallow,
                crawl_delay=current_crawl_delay,
            ))
        
        return rules
    
    def _extract_sitemaps(self, content: str) -> list[str]:
        """
        Extract sitemap URLs from robots.txt.
        
        Args:
            content: Raw robots.txt content
            
        Returns:
            List of sitemap URLs
        """
        sitemaps = []
        
        for line in content.split("\n"):
            line = line.split("#")[0].strip()
            if not line:
                continue
            
            if ":" not in line:
                continue
            
            directive, value = line.split(":", 1)
            directive = directive.strip().lower()
            value = value.strip()
            
            if directive == "sitemap":
                sitemaps.append(value)
        
        return sitemaps
    
    def is_allowed(
        self,
        url: str,
        robots_data: RobotsData,
        user_agent: str = "*",
    ) -> bool:
        """
        Check if a URL is allowed by robots.txt rules.
        
        Args:
            url: URL to check
            robots_data: Parsed robots.txt data
            user_agent: User agent to check for
            
        Returns:
            True if URL is allowed, False otherwise
        """
        if not robots_data.accessible:
            # If we couldn't fetch robots.txt, assume allowed
            return True
        
        if not robots_data.rules:
            # No rules means everything is allowed
            return True
        
        # Extract path from URL
        parsed = urlparse(url)
        path = parsed.path or "/"
        
        # Find matching rules (specific user-agent first, then *)
        matching_rules = []
        for rule in robots_data.rules:
            if rule.user_agent.lower() in (user_agent.lower(), "*"):
                matching_rules.append(rule)
        
        if not matching_rules:
            return True
        
        # Check disallow rules first (more specific)
        for rule in matching_rules:
            for pattern in rule.disallow:
                if self._matches_pattern(path, pattern):
                    # Check if there's a more specific allow rule
                    for allow_pattern in rule.allow:
                        if self._matches_pattern(path, allow_pattern):
                            if len(allow_pattern) > len(pattern):
                                return True
                    return False
        
        return True
    
    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """
        Check if a path matches a robots.txt pattern.
        
        Args:
            path: URL path to check
            pattern: robots.txt pattern (with * and $ wildcards)
            
        Returns:
            True if path matches pattern
        """
        if not pattern:
            return True
        
        # Handle $ (end of URL) - must match exactly at the end
        ends_with_dollar = pattern.endswith("$")
        if ends_with_dollar:
            pattern = pattern[:-1]
        
        # Handle * (wildcard)
        if "*" in pattern:
            parts = pattern.split("*")
            pos = 0
            for i, part in enumerate(parts):
                if not part:
                    continue
                
                # For the last part, if we have $, it must be at the end
                if i == len(parts) - 1 and ends_with_dollar:
                    if not path.endswith(part):
                        return False
                else:
                    idx = path.find(part, pos)
                    if idx == -1:
                        return False
                    pos = idx + len(part)
            return True
        
        # Simple prefix or exact match
        if ends_with_dollar:
            return path == pattern
        else:
            return path.startswith(pattern)
