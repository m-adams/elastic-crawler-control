"""
Site Investigation Agent (Agno-powered).

Investigates target websites to understand structure, content patterns, and crawlability.
Uses Agno Agent with tools to analyze page structure and generate recommendations.

This module provides both:
- SiteInvestigationAgent: High-level class maintaining backward compatibility
- create_site_investigation_agent(): Factory for creating the underlying Agno agent

The agent uses the following tools:
- fetch_robots_txt: Fetch and parse robots.txt
- fetch_sitemap_urls: Parse sitemaps for page URLs
- fetch_pages: Fetch sample pages with rate limiting
- analyze_page_structure: Analyze HTML structure
- analyze_page_patterns: Find patterns across pages
- select_sample_urls: Choose representative pages
- generate_recommendations: Create crawl rule suggestions
"""

import json
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from agno.agent import Agent

from utils.agno_model import get_model, is_agno_available
from utils.robots_parser import RobotsParser, RobotsData
from utils.sitemap_parser import SitemapParser, SitemapURL
from utils.page_fetcher import PageFetcher, PageFetchResult
from utils.html_analyzer import HTMLAnalyzer, PageStructure
from utils.llm_client import LLMClient

from agents.site_investigation_tools import (
    fetch_robots_txt,
    fetch_sitemap_urls,
    fetch_pages,
    analyze_page_structure,
    analyze_page_patterns,
    select_sample_urls,
    generate_recommendations,
    SITE_INVESTIGATION_TOOLS,
    reset_tool_instances,
)


# Agent instructions for LLM-powered investigation
SITE_INVESTIGATION_INSTRUCTIONS = [
    "You are a Site Investigation Agent that analyzes websites to prepare for web crawling.",
    "Your goal is to understand the website's structure, content patterns, and crawlability.",
    "",
    "When investigating a domain, follow these steps:",
    "1. First, fetch the robots.txt to understand crawl rules and find sitemaps",
    "2. If sitemaps exist, fetch them to discover available pages",
    "3. Select a representative sample of pages to analyze",
    "4. Fetch the sample pages",
    "5. Analyze each page's HTML structure",
    "6. Analyze patterns across all pages",
    "7. Generate recommendations for crawling configuration",
    "",
    "Always provide structured analysis including:",
    "- Content type assessment (blog, documentation, e-commerce, etc.)",
    "- Key content areas and their CSS selectors",
    "- Metadata availability (titles, descriptions, authors, dates)",
    "- Navigation structure",
    "- Potential crawling challenges",
    "- Recommended extraction rules",
    "",
    "Be thorough but efficient. Focus on actionable insights for crawler configuration.",
]


def create_site_investigation_agent(
    model_id: Optional[str] = None,
    debug_mode: bool = False,
) -> Agent:
    """
    Create an Agno Site Investigation Agent.
    
    This factory function creates a fully configured Agno Agent for site investigation.
    The agent has access to all site investigation tools and uses the LLM Proxy model.
    
    Args:
        model_id: Optional override for the LLM model ID
        debug_mode: If True, enable debug output
        
    Returns:
        Configured Agno Agent instance
        
    Raises:
        ValueError: If LLM Proxy API key is not configured
        
    Example:
        >>> agent = create_site_investigation_agent()
        >>> response = agent.run("Investigate https://example.com")
        >>> print(response.content)
    """
    model = get_model(model_id=model_id, temperature=0.3)
    
    return Agent(
        model=model,
        name="SiteInvestigationAgent",
        description="Investigates websites to understand structure, content patterns, and crawlability",
        instructions=SITE_INVESTIGATION_INSTRUCTIONS,
        tools=SITE_INVESTIGATION_TOOLS,
        markdown=True,
        debug_mode=debug_mode,
    )


class SiteInvestigationAgent:
    """
    Agent for investigating websites before crawl configuration.
    
    This class provides a high-level interface for site investigation that
    maintains backward compatibility with the original implementation while
    using Agno tools under the hood.
    
    The agent can operate in two modes:
    1. LLM-powered: Uses Agno Agent for intelligent analysis (when API key available)
    2. Tool-based: Uses tools directly for deterministic analysis (fallback)
    
    Performs:
    - robots.txt analysis
    - sitemap discovery
    - Page structure analysis
    - Content pattern detection
    - Crawl rule recommendations
    
    Example:
        >>> agent = SiteInvestigationAgent()
        >>> result = await agent.investigate("https://example.com")
        >>> print(result["status"])
        'completed'
    """
    
    def __init__(
        self,
        sample_page_count: int = 10,
        rate_limit_delay: float = 1.0,
        llm_client: Optional[LLMClient] = None,
        use_agno: bool = True,
        debug_mode: bool = False,
    ):
        """
        Initialize site investigation agent.
        
        Args:
            sample_page_count: Number of sample pages to fetch per domain
            rate_limit_delay: Delay between page requests in seconds
            llm_client: Optional legacy LLM client (deprecated, use Agno)
            use_agno: Whether to use Agno for LLM analysis (default: True)
            debug_mode: Enable debug output for Agno agent
        """
        self.sample_page_count = sample_page_count
        self.rate_limit_delay = rate_limit_delay
        self.use_agno = use_agno and is_agno_available()
        self.debug_mode = debug_mode
        
        # Keep legacy llm_client for backward compatibility
        self.llm_client = llm_client
        
        # Initialize utilities for direct tool calls
        self.robots_parser = RobotsParser()
        self.sitemap_parser = SitemapParser()
        self.page_fetcher = PageFetcher(rate_limit_delay=rate_limit_delay)
        self.html_analyzer = HTMLAnalyzer()
        
        # Agno agent (lazy initialized)
        self._agno_agent: Optional[Agent] = None
    
    def _get_agno_agent(self) -> Agent:
        """Get or create the Agno agent instance."""
        if self._agno_agent is None:
            self._agno_agent = create_site_investigation_agent(debug_mode=self.debug_mode)
        return self._agno_agent
    
    async def investigate(
        self,
        domain: str,
        seed_urls: list[str] | None = None,
    ) -> Dict[str, Any]:
        """
        Investigate a target domain to understand its structure.
        
        This method orchestrates the full investigation workflow using the
        underlying tools. It maintains backward compatibility with the original
        API while leveraging Agno tools for each step.
        
        Args:
            domain: Target domain to investigate (e.g., "https://example.com")
            seed_urls: Optional seed URLs to start from
            
        Returns:
            Site analysis report containing:
            - robots_txt: Parsed robots.txt rules
            - sitemaps: Discovered sitemap URLs and structure
            - page_samples: Sample pages analyzed
            - page_structure_analysis: Common HTML patterns found
            - llm_analysis: LLM-powered insights (if available)
            - recommendations: Suggested crawl rules and extraction patterns
        """
        # Normalize domain
        if not domain.startswith(("http://", "https://")):
            domain = f"https://{domain}"
        
        parsed_domain = urlparse(domain)
        domain_name = parsed_domain.netloc
        
        report = {
            "domain": domain,
            "domain_name": domain_name,
            "seed_urls": seed_urls or [],
            "status": "investigating",
        }
        
        # Phase 1: Fetch and analyze robots.txt
        print(f"Investigating {domain}: Fetching robots.txt...")
        robots_data = await self.robots_parser.fetch_and_parse(domain)
        report["robots_txt"] = self._format_robots_data(robots_data)
        
        if not robots_data.accessible:
            report["status"] = "error"
            report["error"] = robots_data.error
            return report
        
        # Phase 2: Discover and parse sitemaps
        print(f"Investigating {domain}: Parsing sitemaps...")
        sitemap_urls = robots_data.sitemaps
        
        if sitemap_urls:
            all_sitemap_urls = await self.sitemap_parser.fetch_all_urls(
                sitemap_urls,
                max_depth=1,  # Don't go too deep
            )
            report["sitemaps"] = {
                "sitemap_urls": sitemap_urls,
                "total_urls_found": len(all_sitemap_urls),
                "sample_urls": [url.loc for url in all_sitemap_urls[:20]],
            }
        else:
            all_sitemap_urls = []
            report["sitemaps"] = {
                "sitemap_urls": [],
                "total_urls_found": 0,
                "sample_urls": [],
            }
        
        # Phase 3: Select sample pages to fetch
        print(f"Investigating {domain}: Selecting sample pages...")
        sample_urls = self._select_sample_urls(
            domain,
            seed_urls,
            all_sitemap_urls,
            self.sample_page_count,
        )
        
        # Phase 4: Fetch sample pages
        print(f"Investigating {domain}: Fetching {len(sample_urls)} sample pages...")
        fetch_result = await self.page_fetcher.fetch_pages(sample_urls)
        
        if fetch_result.bot_protection_detected:
            report["status"] = "warning"
            report["warning"] = "Bot protection detected on some pages"
        
        report["page_fetch_summary"] = {
            "total_attempted": len(sample_urls),
            "successful": fetch_result.successful,
            "failed": fetch_result.failed,
            "bot_protection_detected": fetch_result.bot_protection_detected,
        }
        
        # Phase 5: Analyze page structure
        print(f"Investigating {domain}: Analyzing page structure...")
        page_structures = []
        for page in fetch_result.pages:
            if page.html_content and not page.error:
                structure = self.html_analyzer.analyze_page(page.url, page.html_content)
                page_structures.append(structure)
        
        # Analyze patterns across pages
        pattern_analysis = self.html_analyzer.analyze_patterns(page_structures)
        report["page_structure_analysis"] = pattern_analysis
        
        # Include sample page structures
        report["page_samples"] = [
            self._format_page_structure(struct)
            for struct in page_structures[:3]  # First 3 pages
        ]
        
        # Phase 6: LLM analysis (if available)
        if self.use_agno:
            print(f"Investigating {domain}: Running Agno LLM analysis...")
            try:
                llm_analysis = await self._analyze_with_agno(
                    domain,
                    robots_data,
                    page_structures,
                    pattern_analysis,
                )
                report["llm_analysis"] = llm_analysis
            except Exception as e:
                report["llm_analysis"] = {
                    "status": "error",
                    "error": str(e),
                }
        elif self.llm_client:
            # Legacy LLM client fallback
            print(f"Investigating {domain}: Running legacy LLM analysis...")
            try:
                llm_analysis = await self._analyze_with_llm(
                    domain,
                    robots_data,
                    page_structures,
                    pattern_analysis,
                )
                report["llm_analysis"] = llm_analysis
            except Exception as e:
                report["llm_analysis"] = {
                    "status": "error",
                    "error": str(e),
                }
        else:
            report["llm_analysis"] = {
                "status": "disabled",
                "message": "LLM analysis not available (no API key configured)",
            }
        
        # Phase 7: Generate basic recommendations
        report["recommendations"] = self._generate_recommendations(
            domain,
            robots_data,
            page_structures,
            pattern_analysis,
        )
        
        report["status"] = "completed"
        return report
    
    def _select_sample_urls(
        self,
        domain: str,
        seed_urls: Optional[list[str]],
        sitemap_urls: list[SitemapURL],
        sample_count: int,
    ) -> list[str]:
        """
        Select sample URLs to fetch.
        
        Priority:
        1. Seed URLs (if provided)
        2. URLs from sitemap (distributed sampling)
        3. Homepage as fallback
        """
        selected = []
        
        # Add seed URLs first
        if seed_urls:
            selected.extend(seed_urls[:sample_count])
        
        # Add URLs from sitemap
        if len(selected) < sample_count and sitemap_urls:
            sitemap_url_strings = [url.loc for url in sitemap_urls]
            remaining = sample_count - len(selected)
            
            if len(sitemap_url_strings) <= remaining:
                selected.extend(sitemap_url_strings)
            else:
                # Distributed sampling
                step = len(sitemap_url_strings) / remaining
                indices = [int(i * step) for i in range(remaining)]
                selected.extend([sitemap_url_strings[i] for i in indices])
        
        # Add homepage if we still don't have enough
        if not selected:
            selected.append(domain)
        
        return selected
    
    def _format_robots_data(self, robots_data: RobotsData) -> dict:
        """Format robots.txt data for report."""
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
    
    def _format_page_structure(self, structure: PageStructure) -> dict:
        """Format page structure for report."""
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
                for area in structure.content_areas[:3]
            ],
            "navigation_selectors": structure.navigation_selectors,
            "stats": {
                "total_links": structure.total_links,
                "total_images": structure.total_images,
                "text_length": structure.text_length,
            },
        }
    
    def _generate_recommendations(
        self,
        domain: str,
        robots_data: RobotsData,
        page_structures: list[PageStructure],
        pattern_analysis: dict,
    ) -> dict:
        """
        Generate basic recommendations without LLM.
        
        This provides fallback recommendations when LLM is not available.
        """
        recommendations = {
            "crawl_rules": [],
            "extraction_rules": [],
            "challenges": [],
        }
        
        # Crawl rule recommendations based on robots.txt
        if robots_data.rules:
            for rule in robots_data.rules:
                if rule.disallow:
                    recommendations["crawl_rules"].append({
                        "type": "exclude_paths",
                        "patterns": rule.disallow,
                        "reason": f"Disallowed by robots.txt for {rule.user_agent}",
                    })
                
                if rule.crawl_delay:
                    recommendations["crawl_rules"].append({
                        "type": "crawl_delay",
                        "value": rule.crawl_delay,
                        "reason": f"Recommended by robots.txt for {rule.user_agent}",
                    })
        
        # Extraction recommendations based on patterns
        if page_structures:
            # Check for common metadata
            metadata_fields = []
            for struct in page_structures:
                if struct.metadata.title:
                    metadata_fields.append("title")
                if struct.metadata.description:
                    metadata_fields.append("description")
                if struct.metadata.author:
                    metadata_fields.append("author")
                if struct.metadata.published_date:
                    metadata_fields.append("date")
            
            if metadata_fields:
                recommendations["extraction_rules"].append({
                    "type": "metadata_extraction",
                    "fields": list(set(metadata_fields)),
                    "reason": "Common metadata fields detected",
                })
            
            # Check for content areas
            if pattern_analysis.get("common_content_tags"):
                recommendations["extraction_rules"].append({
                    "type": "content_extraction",
                    "tags": [tag["tag"] for tag in pattern_analysis["common_content_tags"][:3]],
                    "reason": "Common content area tags detected",
                })
        
        return recommendations
    
    async def _analyze_with_agno(
        self,
        domain: str,
        robots_data: RobotsData,
        page_structures: list[PageStructure],
        pattern_analysis: dict,
    ) -> dict:
        """
        Use Agno Agent to analyze the site and generate recommendations.
        """
        # Prepare summary for LLM
        summary = {
            "domain": domain,
            "robots_txt_summary": {
                "has_rules": len(robots_data.rules) > 0,
                "sitemap_count": len(robots_data.sitemaps),
                "disallowed_paths": [
                    path
                    for rule in robots_data.rules
                    for path in rule.disallow
                ],
            },
            "pages_analyzed": len(page_structures),
            "pattern_analysis": pattern_analysis,
            "sample_pages": [
                self._format_page_structure(struct)
                for struct in page_structures[:2]
            ],
        }
        
        # Create prompt for analysis
        prompt = f"""Analyze this website investigation report and provide recommendations for web crawling configuration.

Website: {domain}

Investigation Summary:
{json.dumps(summary, indent=2)}

Please provide:
1. Content Type Analysis: What types of content does this site have? (e.g., blog articles, product pages, documentation)
2. Extraction Recommendations: What fields should be extracted from pages? Suggest CSS selectors or patterns.
3. Crawl Strategy: How should the crawler navigate this site? What patterns should be followed or avoided?
4. Potential Challenges: What issues might arise during crawling? (bot protection, dynamic content, etc.)

Format your response as structured recommendations."""
        
        # Get or create agent and run analysis
        agent = self._get_agno_agent()
        response = agent.run(prompt)
        
        # Extract content from response
        content = response.content if hasattr(response, 'content') else str(response)
        
        return {
            "status": "completed",
            "analysis": content,
        }
    
    async def _analyze_with_llm(
        self,
        domain: str,
        robots_data: RobotsData,
        page_structures: list[PageStructure],
        pattern_analysis: dict,
    ) -> dict:
        """
        Use legacy LLM client to analyze the site and generate recommendations.
        (Kept for backward compatibility)
        """
        # Prepare summary for LLM
        summary = {
            "domain": domain,
            "robots_txt_summary": {
                "has_rules": len(robots_data.rules) > 0,
                "sitemap_count": len(robots_data.sitemaps),
                "disallowed_paths": [
                    path
                    for rule in robots_data.rules
                    for path in rule.disallow
                ],
            },
            "pages_analyzed": len(page_structures),
            "pattern_analysis": pattern_analysis,
            "sample_pages": [
                self._format_page_structure(struct)
                for struct in page_structures[:2]
            ],
        }
        
        # Create prompt for LLM
        prompt = f"""Analyze this website investigation report and provide recommendations for web crawling configuration.

Website: {domain}

Investigation Summary:
{json.dumps(summary, indent=2)}

Please provide:
1. Content Type Analysis: What types of content does this site have? (e.g., blog articles, product pages, documentation)
2. Extraction Recommendations: What fields should be extracted from pages? Suggest CSS selectors or patterns.
3. Crawl Strategy: How should the crawler navigate this site? What patterns should be followed or avoided?
4. Potential Challenges: What issues might arise during crawling? (bot protection, dynamic content, etc.)

Format your response as structured recommendations."""
        
        messages = [
            {
                "role": "user",
                "content": prompt,
            }
        ]
        
        # Call LLM (non-streaming for analysis)
        full_response = ""
        async for chunk in self.llm_client.chat_completion(
            messages=messages,
            stream=True,
            temperature=0.3,  # Lower temperature for more focused analysis
        ):
            if "choices" in chunk and len(chunk["choices"]) > 0:
                delta = chunk["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    full_response += content
        
        return {
            "status": "completed",
            "analysis": full_response,
        }
