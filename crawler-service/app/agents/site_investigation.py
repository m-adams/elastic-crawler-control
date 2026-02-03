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
from utils.logging import get_logger

logger = get_logger(__name__)


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
        preflight_data: dict | None = None,
        user_context: str | None = None,
    ) -> Dict[str, Any]:
        """
        Investigate a target domain to understand its structure.
        
        This method orchestrates the full investigation workflow using the
        underlying tools. It maintains backward compatibility with the original
        API while leveraging Agno tools for each step.
        
        Args:
            domain: Target domain to investigate (e.g., "https://example.com")
            seed_urls: Optional seed URLs to start from
            preflight_data: Optional preflight results (contains robots.txt to avoid re-fetch)
            user_context: Optional user description of their goals/use case for crawling
            
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
            "user_context": user_context,
            "status": "investigating",
        }
        
        # Phase 1: Get robots.txt (use preflight data if available to avoid re-fetch)
        if preflight_data and preflight_data.get("robots_txt"):
            logger.info("Using robots.txt from preflight (avoiding re-fetch)", domain=domain)
            robots_txt_data = preflight_data["robots_txt"]
            # Convert preflight format to RobotsData
            robots_data = RobotsData(
                accessible=robots_txt_data.get("exists", True),
                sitemaps=robots_txt_data.get("sitemap_urls", []),
                rules=[],  # Preflight only stores summary, not full rules
                error=None,
            )
            # If preflight has blocked_paths, we need to create rules
            if robots_txt_data.get("blocked_paths"):
                from utils.robots_parser import RobotsRule
                robots_data.rules.append(RobotsRule(
                    user_agent="*",
                    allow=[],
                    disallow=robots_txt_data.get("blocked_paths", []),
                    crawl_delay=robots_txt_data.get("crawl_delay"),
                ))
            report["robots_txt"] = self._format_robots_data(robots_data)
            report["robots_txt"]["from_preflight"] = True
        else:
            logger.info("Fetching robots.txt", domain=domain)
            robots_data = await self.robots_parser.fetch_and_parse(domain)
            report["robots_txt"] = self._format_robots_data(robots_data)
            
            if not robots_data.accessible:
                logger.warning("robots.txt not accessible", domain=domain, error=robots_data.error)
                report["status"] = "error"
                report["error"] = robots_data.error
                return report
        
        # Phase 2: Discover and parse sitemaps
        logger.info("Parsing sitemaps", domain=domain, sitemap_count=len(robots_data.sitemaps))
        sitemap_urls = robots_data.sitemaps
        
        if sitemap_urls:
            all_sitemap_urls = await self.sitemap_parser.fetch_all_urls(
                sitemap_urls,
                max_depth=1,  # Don't go too deep
            )
            report["sitemaps"] = {
                "sitemap_urls": sitemap_urls,
                "total_urls_found": len(all_sitemap_urls),
                "sample_urls": [url.loc for url in all_sitemap_urls[:200]],  # Store more for extraction planning
            }
            logger.debug("Sitemaps parsed", urls_found=len(all_sitemap_urls))
        else:
            all_sitemap_urls = []
            report["sitemaps"] = {
                "sitemap_urls": [],
                "total_urls_found": 0,
                "sample_urls": [],
            }
            logger.debug("No sitemaps found")
        
        # Phase 3: Select sample pages to fetch
        sample_urls = self._select_sample_urls(
            domain,
            seed_urls,
            all_sitemap_urls,
            self.sample_page_count,
        )
        logger.info("Selected sample pages", domain=domain, count=len(sample_urls))
        
        # Phase 4: Fetch sample pages
        logger.info("Fetching sample pages", domain=domain, count=len(sample_urls))
        fetch_result = await self.page_fetcher.fetch_pages(sample_urls)
        
        if fetch_result.bot_protection_detected:
            logger.warning("Bot protection detected", domain=domain)
            report["status"] = "warning"
            report["warning"] = "Bot protection detected on some pages"
        
        report["page_fetch_summary"] = {
            "total_attempted": len(sample_urls),
            "successful": fetch_result.successful,
            "failed": fetch_result.failed,
            "bot_protection_detected": fetch_result.bot_protection_detected,
        }
        logger.info(
            "Page fetch complete",
            domain=domain,
            successful=fetch_result.successful,
            failed=fetch_result.failed,
        )
        
        # Phase 5: Analyze page structure
        logger.info("Analyzing page structure", domain=domain, pages=fetch_result.successful)
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
        
        # Include raw HTML samples for LLM extraction rule generation
        # Prioritize content pages over section/topic pages for better extraction rules
        report["html_samples"] = self._select_html_samples_for_extraction(
            fetch_result.pages, domain, max_samples=3
        )
        logger.debug("Stored HTML samples for extraction", count=len(report["html_samples"]))
        
        # Phase 6: LLM analysis (if available)
        if self.use_agno:
            logger.info("Running Agno LLM analysis", domain=domain, has_user_context=bool(user_context))
            try:
                llm_analysis = await self._analyze_with_agno(
                    domain,
                    robots_data,
                    page_structures,
                    pattern_analysis,
                    user_context=user_context,
                )
                report["llm_analysis"] = llm_analysis
                logger.debug("LLM analysis complete", domain=domain, status="completed")
            except Exception as e:
                logger.exception("LLM analysis failed", domain=domain)
                report["llm_analysis"] = {
                    "status": "error",
                    "error": str(e),
                }
        elif self.llm_client:
            # Legacy LLM client fallback
            logger.info("Running legacy LLM analysis", domain=domain)
            try:
                llm_analysis = await self._analyze_with_llm(
                    domain,
                    robots_data,
                    page_structures,
                    pattern_analysis,
                )
                report["llm_analysis"] = llm_analysis
            except Exception as e:
                logger.exception("Legacy LLM analysis failed", domain=domain)
                report["llm_analysis"] = {
                    "status": "error",
                    "error": str(e),
                }
        else:
            logger.debug("LLM analysis disabled (no API key)", domain=domain)
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
    
    def _select_html_samples_for_extraction(
        self,
        pages: list,
        domain: str,
        max_samples: int = 3,
    ) -> list[dict]:
        """
        Select HTML samples for extraction rule generation.
        
        Prioritizes actual content pages over section/navigation pages.
        This ensures the LLM sees representative content when designing
        extraction rules, not just homepage or category pages.
        
        Args:
            pages: List of fetched page objects
            domain: The target domain
            max_samples: Maximum number of HTML samples to store
        
        Returns:
            List of HTML sample dicts with url, html, and full_length
        """
        import re
        from urllib.parse import urlparse
        
        def score_page_for_extraction(page) -> tuple[int, int]:
            """
            Score a page for extraction suitability.
            Higher score = more likely to be useful content page.
            
            Returns (score, content_length) for sorting.
            """
            if not page.html_content or page.error:
                return (-1000, 0)
            
            url = page.url
            parsed = urlparse(url)
            path = parsed.path.rstrip('/')
            
            score = 0
            
            # Penalize homepage/root
            if not path or path == '':
                score -= 100
            
            # Penalize short paths (likely section pages like /sport, /news)
            path_segments = [s for s in path.split('/') if s]
            if len(path_segments) <= 1:
                score -= 50
            elif len(path_segments) >= 3:
                score += 30  # Deeper paths more likely to be content
            
            # Reward paths that look like articles
            article_patterns = [
                r'/article', r'/news/', r'/story/', r'/post/',
                r'/blog/', r'/\d{4}/\d{2}/',  # Date patterns like /2024/01/
                r'/p/\w+', r'/a/\w+',  # Short article IDs
            ]
            for pattern in article_patterns:
                if re.search(pattern, path, re.IGNORECASE):
                    score += 50
                    break
            
            # Penalize paths that look like navigation/sections
            nav_patterns = [
                r'^/topics?/?$', r'^/categor', r'^/tag/?$',
                r'^/search', r'^/about', r'^/contact',
                r'^/[a-z]+/?$',  # Single-word top-level paths
            ]
            for pattern in nav_patterns:
                if re.search(pattern, path, re.IGNORECASE):
                    score -= 30
                    break
            
            # Reward longer content (articles tend to be longer)
            content_length = len(page.html_content)
            if content_length > 100000:
                score += 20
            elif content_length > 50000:
                score += 10
            
            # Check for article indicators in HTML
            html_lower = page.html_content[:5000].lower()  # Check first 5k chars
            if '<article' in html_lower:
                score += 40
            if 'itemprop="article' in html_lower or 'itemtype="http://schema.org/article' in html_lower:
                score += 40
            if '"@type":"article' in html_lower or '"@type": "article' in html_lower:
                score += 40
            if 'class="author' in html_lower or 'rel="author' in html_lower:
                score += 20
            if 'datetime=' in html_lower or 'publisheddate' in html_lower:
                score += 20
            
            return (score, content_length)
        
        # Score and sort pages
        scored_pages = []
        for page in pages:
            if page.html_content and not page.error:
                score, content_len = score_page_for_extraction(page)
                scored_pages.append((score, content_len, page))
        
        # Sort by score descending, then content length descending
        scored_pages.sort(key=lambda x: (x[0], x[1]), reverse=True)
        
        # Take top pages
        html_samples = []
        for score, content_len, page in scored_pages[:max_samples]:
            # Truncate to avoid overwhelming LLM context
            html_snippet = page.html_content[:15000]
            if len(page.html_content) > 15000:
                html_snippet += "\n<!-- ... HTML truncated ... -->"
            
            html_samples.append({
                "url": page.url,
                "html": html_snippet,
                "full_length": len(page.html_content),
                "extraction_score": score,  # Include for debugging
            })
            
            logger.debug(
                "Selected HTML sample for extraction",
                url=page.url,
                score=score,
                content_length=content_len,
            )
        
        return html_samples
    
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
        # Only use rules for User-agent: * (not bot-specific blocks like ClaudeBot, GPTBot)
        if robots_data.rules:
            for rule in robots_data.rules:
                # Only apply rules for the wildcard user-agent
                # Skip bot-specific blocks (e.g., "ClaudeBot", "GPTBot", "Scrapy")
                if rule.user_agent != "*":
                    continue
                
                if rule.disallow:
                    # Filter out overly broad disallows like "/" which would block everything
                    meaningful_disallows = [
                        pattern for pattern in rule.disallow 
                        if pattern and pattern != "/" and len(pattern) > 1
                    ]
                    if meaningful_disallows:
                        recommendations["crawl_rules"].append({
                            "type": "exclude_paths",
                            "patterns": meaningful_disallows,
                            "reason": "Disallowed by robots.txt",
                        })
                
                if rule.crawl_delay:
                    recommendations["crawl_rules"].append({
                        "type": "crawl_delay",
                        "value": rule.crawl_delay,
                        "reason": "Recommended crawl delay from robots.txt",
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
        user_context: str | None = None,
    ) -> dict:
        """
        Use Agno Agent to analyze the site and generate recommendations.
        
        Args:
            domain: Target domain
            robots_data: Parsed robots.txt data
            page_structures: Analyzed page structures
            pattern_analysis: Patterns found across pages
            user_context: Optional user description of their goals/use case
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
        
        # Build user context section if provided
        user_context_section = ""
        if user_context:
            user_context_section = f"""
USER'S GOALS AND USE CASE:
{user_context}

IMPORTANT: Your analysis should be tailored to help achieve the user's stated goals above.
Focus on finding content and patterns that match what they want to crawl.
"""
        
        # Create prompt for analysis
        # Build conditional suffixes (f-strings can't have backslash escapes)
        content_suffix = " Focus on content relevant to the user's goals." if user_context else ""
        extraction_suffix = " Prioritize fields that match the user's stated needs." if user_context else ""
        crawl_suffix = " Consider the user's focus areas." if user_context else ""
        
        prompt = f"""Analyze this website investigation report and provide recommendations for web crawling configuration.
{user_context_section}
Website: {domain}

Investigation Summary:
{json.dumps(summary, indent=2)}

Please provide:
1. Content Type Analysis: What types of content does this site have? (e.g., blog articles, product pages, documentation){content_suffix}
2. Extraction Recommendations: What fields should be extracted from pages? Suggest CSS selectors or patterns.{extraction_suffix}
3. Crawl Strategy: How should the crawler navigate this site? What patterns should be followed or avoided?{crawl_suffix}
4. Potential Challenges: What issues might arise during crawling? (bot protection, dynamic content, etc.)

Format your response as structured recommendations."""
        
        # Get or create agent and run analysis (using async method)
        agent = self._get_agno_agent()
        response = await agent.arun(prompt)
        
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
