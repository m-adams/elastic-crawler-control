"""
Agents package for the Elastic Crawler Service.

This package contains Agno-powered agents:
- site_investigation: Investigates websites to understand structure and content
- site_investigation_tools: Agno tools for site investigation

The agents use the Agno framework with the Elastic LLM Proxy for AI capabilities.
"""

from agents.site_investigation import (
    SiteInvestigationAgent,
    create_site_investigation_agent,
    SITE_INVESTIGATION_INSTRUCTIONS,
)
from agents.site_investigation_tools import (
    fetch_robots_txt,
    fetch_sitemap_urls,
    fetch_pages,
    analyze_page_structure,
    analyze_page_patterns,
    select_sample_urls,
    generate_recommendations,
    SITE_INVESTIGATION_TOOLS,
)

__all__ = [
    # Agent class
    "SiteInvestigationAgent",
    "create_site_investigation_agent",
    "SITE_INVESTIGATION_INSTRUCTIONS",
    # Tools
    "fetch_robots_txt",
    "fetch_sitemap_urls",
    "fetch_pages",
    "analyze_page_structure",
    "analyze_page_patterns",
    "select_sample_urls",
    "generate_recommendations",
    "SITE_INVESTIGATION_TOOLS",
]
