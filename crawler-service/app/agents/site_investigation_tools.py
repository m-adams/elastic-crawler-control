"""
Agno tools for site investigation.

This module wraps the existing utility classes (robots_parser, sitemap_parser,
page_fetcher, html_analyzer) as standalone Agno-compatible tool functions.

Each tool function:
- Has a detailed docstring for LLM understanding
- Takes simple parameters and returns JSON-serializable results
- Handles errors gracefully and returns structured error responses

Usage:
    from agents.site_investigation_tools import (
        fetch_robots_txt,
        fetch_sitemap_urls,
        fetch_pages,
        analyze_page_structure,
        analyze_page_patterns,
    )
    
    from agno.agent import Agent
    agent = Agent(
        model=model,
        tools=[fetch_robots_txt, fetch_sitemap_urls, ...],
    )
"""

import asyncio
import json
from typing import Any, Optional
from urllib.parse import urlparse

from utils.robots_parser import RobotsParser, RobotsData
from utils.sitemap_parser import SitemapParser, SitemapURL
from utils.page_fetcher import PageFetcher
from utils.html_analyzer import HTMLAnalyzer, PageStructure


# Module-level instances (lazy initialized)
_robots_parser: Optional[RobotsParser] = None
_sitemap_parser: Optional[SitemapParser] = None
_page_fetcher: Optional[PageFetcher] = None
_html_analyzer: Optional[HTMLAnalyzer] = None


def _get_robots_parser() -> RobotsParser:
    """Get or create the robots parser instance."""
    global _robots_parser
    if _robots_parser is None:
        _robots_parser = RobotsParser()
    return _robots_parser


def _get_sitemap_parser() -> SitemapParser:
    """Get or create the sitemap parser instance."""
    global _sitemap_parser
    if _sitemap_parser is None:
        _sitemap_parser = SitemapParser()
    return _sitemap_parser


def _get_page_fetcher(rate_limit_delay: float = 1.0) -> PageFetcher:
    """Get or create the page fetcher instance."""
    global _page_fetcher
    if _page_fetcher is None:
        _page_fetcher = PageFetcher(rate_limit_delay=rate_limit_delay)
    return _page_fetcher


def _get_html_analyzer() -> HTMLAnalyzer:
    """Get or create the HTML analyzer instance."""
    global _html_analyzer
    if _html_analyzer is None:
        _html_analyzer = HTMLAnalyzer()
    return _html_analyzer


def reset_tool_instances():
    """Reset all tool instances (useful for testing)."""
    global _robots_parser, _sitemap_parser, _page_fetcher, _html_analyzer
    _robots_parser = None
    _sitemap_parser = None
    _page_fetcher = None
    _html_analyzer = None


def _run_async(coro):
    """Run an async coroutine synchronously.
    
    Agno tools are synchronous, but our utilities are async.
    This helper handles running async code in a sync context.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If there's already a running loop, create a new one in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop exists, create one
        return asyncio.run(coro)


def _format_robots_data(robots_data: RobotsData) -> dict:
    """Format RobotsData to a JSON-serializable dict."""
    return {
        "accessible": robots_data.accessible,
        "error": robots_data.error,
        "sitemap_urls": robots_data.sitemaps,
        "rules": [
            {
                "user_agent": rule.user_agent,
                "allow": rule.allow,
                "disallow": rule.disallow,
                "crawl_delay": rule.crawl_delay,
            }
            for rule in robots_data.rules
        ],
    }


def _format_page_structure(structure: PageStructure) -> dict:
    """Format PageStructure to a JSON-serializable dict."""
    return {
        "url": structure.url,
        "headings": structure.headings.to_dict(),
        "metadata": {
            "title": structure.metadata.title,
            "description": structure.metadata.description,
            "author": structure.metadata.author,
            "published_date": structure.metadata.published_date,
        },
        "content_areas": [
            {
                "selector": area.selector,
                "tag": area.tag,
                "classes": area.classes,
                "text_length": area.text_length,
            }
            for area in structure.content_areas[:5]  # Limit to top 5
        ],
        "navigation_selectors": structure.navigation_selectors,
        "stats": {
            "total_links": structure.total_links,
            "total_images": structure.total_images,
            "text_length": structure.text_length,
        },
    }


# ============================================================================
# AGNO TOOLS
# ============================================================================


def fetch_robots_txt(domain: str) -> dict:
    """
    Fetch and parse the robots.txt file from a domain.
    
    This tool retrieves the robots.txt file from the target domain and parses it
    to extract crawl rules, sitemap URLs, and crawl delays. Use this as the first
    step when investigating a new website.
    
    Args:
        domain: The target domain URL (e.g., "https://example.com" or "example.com").
                Will be normalized to include https:// if not present.
    
    Returns:
        A dictionary containing:
        - accessible: Whether robots.txt was successfully fetched
        - error: Error message if fetch failed (None if successful)
        - sitemap_urls: List of sitemap URLs found in robots.txt
        - rules: List of crawl rules with user_agent, allow, disallow, and crawl_delay
    
    Example:
        result = fetch_robots_txt("example.com")
        if result["accessible"]:
            print(f"Found {len(result['sitemap_urls'])} sitemaps")
    """
    # Normalize domain
    if not domain.startswith(("http://", "https://")):
        domain = f"https://{domain}"
    
    parser = _get_robots_parser()
    
    try:
        robots_data = _run_async(parser.fetch_and_parse(domain))
        return _format_robots_data(robots_data)
    except Exception as e:
        return {
            "accessible": False,
            "error": f"Failed to fetch robots.txt: {str(e)}",
            "sitemap_urls": [],
            "rules": [],
        }


def fetch_sitemap_urls(sitemap_urls: list[str], max_depth: int = 1) -> dict:
    """
    Fetch and parse sitemap(s) to extract page URLs.
    
    This tool retrieves XML sitemaps and extracts all page URLs from them.
    It can follow nested sitemap indices up to the specified depth.
    Use this after fetching robots.txt to discover all indexable pages.
    
    Args:
        sitemap_urls: List of sitemap URLs to parse (from robots.txt sitemap_urls)
        max_depth: Maximum depth for following nested sitemap indices (default: 1)
    
    Returns:
        A dictionary containing:
        - total_urls_found: Total number of URLs discovered
        - sample_urls: Sample of up to 50 URLs (for review without overwhelming)
        - error: Error message if parsing failed (None if successful)
    
    Example:
        result = fetch_sitemap_urls(["https://example.com/sitemap.xml"])
        print(f"Found {result['total_urls_found']} URLs")
    """
    if not sitemap_urls:
        return {
            "total_urls_found": 0,
            "sample_urls": [],
            "error": None,
        }
    
    parser = _get_sitemap_parser()
    
    try:
        all_urls = _run_async(parser.fetch_all_urls(sitemap_urls, max_depth=max_depth))
        
        return {
            "total_urls_found": len(all_urls),
            "sample_urls": [url.loc for url in all_urls[:50]],  # Sample of 50
            "error": None,
        }
    except Exception as e:
        return {
            "total_urls_found": 0,
            "sample_urls": [],
            "error": f"Failed to parse sitemaps: {str(e)}",
        }


def fetch_pages(urls: list[str], rate_limit_delay: float = 1.0) -> dict:
    """
    Fetch multiple web pages with rate limiting.
    
    This tool fetches HTML content from a list of URLs with automatic rate limiting
    and retry logic. It also detects bot protection mechanisms.
    Use this to sample pages for structure analysis.
    
    Args:
        urls: List of page URLs to fetch
        rate_limit_delay: Delay between requests in seconds (default: 1.0)
    
    Returns:
        A dictionary containing:
        - total_attempted: Number of pages attempted
        - successful: Number of successfully fetched pages
        - failed: Number of failed fetches
        - bot_protection_detected: Whether bot protection was encountered
        - pages: List of fetched page data with url, html_content (truncated), 
                 status_code, and error fields
    
    Example:
        result = fetch_pages(["https://example.com/page1", "https://example.com/page2"])
        print(f"Fetched {result['successful']} of {result['total_attempted']} pages")
    """
    if not urls:
        return {
            "total_attempted": 0,
            "successful": 0,
            "failed": 0,
            "bot_protection_detected": False,
            "pages": [],
        }
    
    # Limit to reasonable number of pages
    urls = urls[:20]
    
    fetcher = _get_page_fetcher(rate_limit_delay)
    
    try:
        result = _run_async(fetcher.fetch_pages(urls))
        
        # Format pages (truncate HTML for LLM context)
        pages = []
        for page in result.pages:
            pages.append({
                "url": page.url,
                "html_content_length": len(page.html_content) if page.html_content else 0,
                "html_preview": page.html_content[:1000] if page.html_content else "",
                "status_code": page.status_code,
                "error": page.error,
            })
        
        return {
            "total_attempted": len(urls),
            "successful": result.successful,
            "failed": result.failed,
            "bot_protection_detected": result.bot_protection_detected,
            "pages": pages,
        }
    except Exception as e:
        return {
            "total_attempted": len(urls),
            "successful": 0,
            "failed": len(urls),
            "bot_protection_detected": False,
            "pages": [],
            "error": f"Failed to fetch pages: {str(e)}",
        }


def analyze_page_structure(url: str, html_content: str) -> dict:
    """
    Analyze the HTML structure of a single page.
    
    This tool parses HTML content and extracts structural information including
    headings, metadata, content areas, and navigation elements.
    Use this to understand the structure of individual pages.
    
    Args:
        url: The page URL (for reference in the result)
        html_content: The raw HTML content to analyze
    
    Returns:
        A dictionary containing:
        - url: The page URL
        - headings: Dict with h1-h6 heading lists
        - metadata: Dict with title, description, author, published_date
        - content_areas: List of identified content areas with selector, tag, classes
        - navigation_selectors: List of CSS selectors for navigation elements
        - stats: Dict with total_links, total_images, text_length
    
    Example:
        result = analyze_page_structure("https://example.com", html_content)
        print(f"Title: {result['metadata']['title']}")
    """
    if not html_content:
        return {
            "url": url,
            "error": "No HTML content provided",
            "headings": {"h1": [], "h2": [], "h3": [], "h4": [], "h5": [], "h6": []},
            "metadata": {"title": None, "description": None, "author": None, "published_date": None},
            "content_areas": [],
            "navigation_selectors": [],
            "stats": {"total_links": 0, "total_images": 0, "text_length": 0},
        }
    
    analyzer = _get_html_analyzer()
    
    try:
        structure = analyzer.analyze_page(url, html_content)
        return _format_page_structure(structure)
    except Exception as e:
        return {
            "url": url,
            "error": f"Failed to analyze page: {str(e)}",
            "headings": {"h1": [], "h2": [], "h3": [], "h4": [], "h5": [], "h6": []},
            "metadata": {"title": None, "description": None, "author": None, "published_date": None},
            "content_areas": [],
            "navigation_selectors": [],
            "stats": {"total_links": 0, "total_images": 0, "text_length": 0},
        }


def analyze_page_patterns(page_structures: list[dict]) -> dict:
    """
    Analyze patterns across multiple page structures.
    
    This tool takes multiple page structure analyses and identifies common patterns
    including shared classes, navigation elements, content tags, and metadata coverage.
    Use this after analyzing several pages to understand site-wide patterns.
    
    Args:
        page_structures: List of page structure dicts (from analyze_page_structure)
    
    Returns:
        A dictionary containing:
        - total_pages_analyzed: Number of pages in the analysis
        - common_classes: List of frequently used CSS classes
        - common_navigation: List of common navigation selectors
        - common_content_tags: List of common content area tags
        - heading_patterns: Dict with avg_h1_count
        - metadata_coverage: Dict with percentages for author, date, description
    
    Example:
        patterns = analyze_page_patterns([struct1, struct2, struct3])
        print(f"Common classes: {patterns['common_classes']}")
    """
    if not page_structures:
        return {
            "total_pages_analyzed": 0,
            "common_classes": [],
            "common_navigation": [],
            "common_content_tags": [],
            "heading_patterns": {"avg_h1_count": 0},
            "metadata_coverage": {"has_author": "0%", "has_date": "0%", "has_description": "0%"},
        }
    
    analyzer = _get_html_analyzer()
    
    # Convert dicts back to PageStructure objects for analysis
    # This is a simplified approach - we use the dict data directly
    from collections import Counter
    
    try:
        # Analyze common classes
        all_classes = []
        for struct in page_structures:
            for area in struct.get("content_areas", []):
                all_classes.extend(area.get("classes", []))
        
        class_counter = Counter(all_classes)
        common_classes = [{"class": cls, "count": count} for cls, count in class_counter.most_common(10)]
        
        # Analyze common navigation patterns
        all_nav_selectors = []
        for struct in page_structures:
            all_nav_selectors.extend(struct.get("navigation_selectors", []))
        
        nav_counter = Counter(all_nav_selectors)
        common_nav = [{"selector": sel, "count": count} for sel, count in nav_counter.most_common(5)]
        
        # Analyze heading patterns
        h1_counts = [len(struct.get("headings", {}).get("h1", [])) for struct in page_structures]
        avg_h1_count = sum(h1_counts) / len(h1_counts) if h1_counts else 0
        
        # Analyze content area patterns
        content_tags = []
        for struct in page_structures:
            for area in struct.get("content_areas", []):
                content_tags.append(area.get("tag", ""))
        
        tag_counter = Counter(content_tags)
        common_content_tags = [{"tag": tag, "count": count} for tag, count in tag_counter.most_common(5)]
        
        # Analyze metadata patterns
        total = len(page_structures)
        has_author = sum(1 for s in page_structures if s.get("metadata", {}).get("author")) / total
        has_date = sum(1 for s in page_structures if s.get("metadata", {}).get("published_date")) / total
        has_description = sum(1 for s in page_structures if s.get("metadata", {}).get("description")) / total
        
        return {
            "total_pages_analyzed": len(page_structures),
            "common_classes": common_classes,
            "common_navigation": common_nav,
            "common_content_tags": common_content_tags,
            "heading_patterns": {
                "avg_h1_count": avg_h1_count,
            },
            "metadata_coverage": {
                "has_author": f"{has_author * 100:.1f}%",
                "has_date": f"{has_date * 100:.1f}%",
                "has_description": f"{has_description * 100:.1f}%",
            },
        }
    except Exception as e:
        return {
            "total_pages_analyzed": len(page_structures),
            "error": f"Failed to analyze patterns: {str(e)}",
            "common_classes": [],
            "common_navigation": [],
            "common_content_tags": [],
            "heading_patterns": {"avg_h1_count": 0},
            "metadata_coverage": {"has_author": "0%", "has_date": "0%", "has_description": "0%"},
        }


def select_sample_urls(
    domain: str,
    seed_urls: list[str] | None,
    sitemap_urls: list[str],
    sample_count: int = 10,
) -> list[str]:
    """
    Select sample URLs to fetch from available sources.
    
    This tool selects a representative sample of URLs from seed URLs and sitemap
    URLs. It prioritizes seed URLs, then uses distributed sampling from sitemaps.
    Use this to choose which pages to fetch for analysis.
    
    Args:
        domain: The target domain (used as fallback if no other URLs available)
        seed_urls: Optional list of seed URLs provided by the user
        sitemap_urls: List of URLs discovered from sitemaps
        sample_count: Number of URLs to select (default: 10)
    
    Returns:
        List of selected URLs (up to sample_count)
    
    Example:
        urls = select_sample_urls("https://example.com", None, sitemap_urls, 10)
        print(f"Selected {len(urls)} URLs to fetch")
    """
    selected = []
    
    # Add seed URLs first
    if seed_urls:
        selected.extend(seed_urls[:sample_count])
    
    # Add URLs from sitemap
    if len(selected) < sample_count and sitemap_urls:
        remaining = sample_count - len(selected)
        
        if len(sitemap_urls) <= remaining:
            selected.extend(sitemap_urls)
        else:
            # Distributed sampling
            step = len(sitemap_urls) / remaining
            indices = [int(i * step) for i in range(remaining)]
            selected.extend([sitemap_urls[i] for i in indices])
    
    # Add homepage if we still don't have any URLs
    if not selected:
        if not domain.startswith(("http://", "https://")):
            domain = f"https://{domain}"
        selected.append(domain)
    
    return selected


def generate_recommendations(
    domain: str,
    robots_data: dict,
    page_structures: list[dict],
    pattern_analysis: dict,
) -> dict:
    """
    Generate basic crawl recommendations based on analysis data.
    
    This tool generates rule-based recommendations without LLM analysis.
    It examines robots.txt rules, page structures, and patterns to suggest
    crawl rules and extraction patterns.
    
    Args:
        domain: The target domain
        robots_data: Parsed robots.txt data (from fetch_robots_txt)
        page_structures: List of page structures (from analyze_page_structure)
        pattern_analysis: Pattern analysis (from analyze_page_patterns)
    
    Returns:
        A dictionary containing:
        - crawl_rules: List of recommended crawl rules
        - extraction_rules: List of recommended extraction rules
        - challenges: List of potential crawling challenges
    
    Example:
        recommendations = generate_recommendations(domain, robots, structures, patterns)
        print(f"Found {len(recommendations['crawl_rules'])} crawl rules")
    """
    recommendations = {
        "crawl_rules": [],
        "extraction_rules": [],
        "challenges": [],
    }
    
    # Crawl rule recommendations based on robots.txt
    rules = robots_data.get("rules", [])
    for rule in rules:
        if rule.get("disallow"):
            recommendations["crawl_rules"].append({
                "type": "exclude_paths",
                "patterns": rule["disallow"],
                "reason": f"Disallowed by robots.txt for {rule.get('user_agent', '*')}",
            })
        
        if rule.get("crawl_delay"):
            recommendations["crawl_rules"].append({
                "type": "crawl_delay",
                "value": rule["crawl_delay"],
                "reason": f"Recommended by robots.txt for {rule.get('user_agent', '*')}",
            })
    
    # Extraction recommendations based on patterns
    if page_structures:
        # Check for common metadata
        metadata_fields = []
        for struct in page_structures:
            metadata = struct.get("metadata", {})
            if metadata.get("title"):
                metadata_fields.append("title")
            if metadata.get("description"):
                metadata_fields.append("description")
            if metadata.get("author"):
                metadata_fields.append("author")
            if metadata.get("published_date"):
                metadata_fields.append("date")
        
        if metadata_fields:
            recommendations["extraction_rules"].append({
                "type": "metadata_extraction",
                "fields": list(set(metadata_fields)),
                "reason": "Common metadata fields detected",
            })
        
        # Check for content areas
        common_tags = pattern_analysis.get("common_content_tags", [])
        if common_tags:
            recommendations["extraction_rules"].append({
                "type": "content_extraction",
                "tags": [tag["tag"] for tag in common_tags[:3]],
                "reason": "Common content area tags detected",
            })
    
    return recommendations


# List of all tools for easy import
SITE_INVESTIGATION_TOOLS = [
    fetch_robots_txt,
    fetch_sitemap_urls,
    fetch_pages,
    analyze_page_structure,
    analyze_page_patterns,
    select_sample_urls,
    generate_recommendations,
]
