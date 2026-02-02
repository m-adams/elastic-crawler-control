"""
Config Validation Agent (Agno-powered).

Validates Open Crawler YAML configurations through schema checks, live page testing,
and crawl rule verification. Uses LLM with reasoning capture for intelligent analysis.

This module provides:
- ConfigValidationAgent: High-level class for config validation
- create_config_validation_agent(): Factory for creating the underlying Agno agent

The agent uses the following tools:
- validate_yaml_syntax: Parse and validate YAML syntax
- validate_schema: Validate against Open Crawler schema
- test_extraction_rules: Test CSS selectors against sample pages
- test_crawl_rules: Verify crawl rule logic against URLs
- generate_validation_report: Create comprehensive validation report
"""

import json
from typing import Any, Dict, List, Optional

import yaml
from agno.agent import Agent

from utils.agno_model import get_model, is_agno_available
from utils.page_fetcher import PageFetcher

from agents.config_validation_tools import (
    validate_yaml_syntax,
    validate_schema,
    check_extraction_rules,
    check_crawl_rules,
    generate_validation_report,
    CONFIG_VALIDATION_TOOLS,
)


# Agent instructions for LLM-powered config validation
CONFIG_VALIDATION_INSTRUCTIONS = [
    "You are a Config Validation Agent that validates Open Crawler YAML configurations.",
    "Your goal is to ensure configurations are valid, will work correctly, and extract the intended data.",
    "",
    "When validating a configuration, follow these steps:",
    "1. First, validate YAML syntax - check for parsing errors",
    "2. Validate schema - check required fields and proper structure",
    "3. If sample pages are provided, test extraction rules against them",
    "4. Test crawl rules against sample URLs to verify logic",
    "5. Generate a comprehensive validation report",
    "",
    "KEY VALIDATION RULES TO CHECK:",
    "- output_sink is required (console, file, or elasticsearch)",
    "- domains is required and must be a non-empty list",
    "- Domain URL must NOT have trailing slash",
    "- ALL extraction rules MUST have 'join_as' field (string or array)",
    "- Field names must NOT use reserved names: id, title, body, url, links, headings",
    "- File output requires max_crawl_depth >= 1",
    "- Crawl rules are evaluated in ORDER - first match wins",
    "- Seed URLs must be allowed by crawl rules",
    "",
    "REPORT YOUR FINDINGS:",
    "- List all errors that must be fixed (blocking issues)",
    "- List warnings that should be reviewed (non-blocking)",
    "- Provide clear recommendations for fixing issues",
    "- Include extraction rule test results if pages were tested",
    "- Note any crawl rule logic issues",
    "",
    "Always provide actionable feedback to help fix any issues found.",
]


def create_config_validation_agent(
    model_id: Optional[str] = None,
    debug_mode: bool = False,
) -> Agent:
    """
    Create an Agno Config Validation Agent.
    
    This factory function creates a fully configured Agno Agent for config validation.
    The agent has access to all config validation tools and uses the LLM Proxy model.
    
    Args:
        model_id: Optional override for the LLM model ID
        debug_mode: If True, enable debug output
        
    Returns:
        Configured Agno Agent instance
        
    Raises:
        ValueError: If LLM Proxy API key is not configured
        
    Example:
        >>> agent = create_config_validation_agent()
        >>> response = agent.run("Validate this config: {yaml_content}")
        >>> print(response.content)
    """
    model = get_model(model_id=model_id, temperature=0.1)  # Low temp for consistent validation
    
    return Agent(
        model=model,
        name="ConfigValidationAgent",
        description="Validates Open Crawler YAML configurations through schema checks and live testing",
        instructions=CONFIG_VALIDATION_INSTRUCTIONS,
        tools=CONFIG_VALIDATION_TOOLS,
        markdown=True,
        debug_mode=debug_mode,
    )


class ConfigValidationAgent:
    """
    Agent for validating Open Crawler configurations.
    
    This class provides a high-level interface for config validation that
    performs schema checks, tests extraction rules against sample pages,
    and verifies crawl rule logic.
    
    The agent can operate in two modes:
    1. LLM-powered: Uses Agno Agent for intelligent analysis (when API key available)
    2. Tool-based: Uses tools directly for deterministic validation (fallback)
    
    Validates:
    - YAML syntax
    - Schema structure and required fields
    - Extraction rule selectors (against sample pages)
    - Crawl rule logic and ordering
    
    Example:
        >>> agent = ConfigValidationAgent()
        >>> result = await agent.validate(yaml_content, sample_pages)
        >>> print(result["overall_status"])
    """
    
    def __init__(
        self,
        use_agno: bool = True,
        debug_mode: bool = False,
        rate_limit_delay: float = 1.0,
    ):
        """
        Initialize config validation agent.
        
        Args:
            use_agno: Whether to use Agno for LLM analysis (default: True)
            debug_mode: Enable debug output for Agno agent
            rate_limit_delay: Delay between page fetches in seconds
        """
        self.use_agno = use_agno and is_agno_available()
        self.debug_mode = debug_mode
        self.rate_limit_delay = rate_limit_delay
        
        # Page fetcher for testing extraction rules
        self.page_fetcher = PageFetcher(rate_limit_delay=rate_limit_delay)
        
        # Agno agent (lazy initialized)
        self._agno_agent: Optional[Agent] = None
    
    def _get_agno_agent(self) -> Agent:
        """Get or create the Agno agent instance."""
        if self._agno_agent is None:
            self._agno_agent = create_config_validation_agent(debug_mode=self.debug_mode)
        return self._agno_agent
    
    async def validate(
        self,
        config_input: str | dict,
        sample_pages: Optional[List[Dict[str, str]]] = None,
        sample_urls: Optional[List[str]] = None,
        fetch_sample_pages: bool = False,
        max_pages_to_fetch: int = 5,
    ) -> Dict[str, Any]:
        """
        Validate an Open Crawler configuration.
        
        This method orchestrates the full validation workflow:
        1. YAML syntax validation
        2. Schema validation
        3. Extraction rule testing (if sample pages provided)
        4. Crawl rule verification
        5. Report generation
        
        Args:
            config_input: YAML string or parsed config dict
            sample_pages: Optional list of page dicts for extraction testing
                         Each dict should have 'url' and 'html_content' keys
            sample_urls: Optional list of URLs for crawl rule testing
            fetch_sample_pages: If True, fetch pages from domain for testing
            max_pages_to_fetch: Max pages to fetch when fetch_sample_pages=True
            
        Returns:
            Validation result containing:
            - overall_status: "pass", "fail", or "warning"
            - yaml_validation: YAML syntax check results
            - schema_validation: Schema validation results
            - extraction_test: Extraction rule test results (if pages provided)
            - crawl_rule_test: Crawl rule test results
            - report: Comprehensive validation report
            - llm_analysis: LLM-generated analysis (if Agno used)
        """
        result = {
            "overall_status": "validating",
        }
        
        # Phase 1: Parse YAML if string input
        print("Config Validation: Checking YAML syntax...")
        if isinstance(config_input, str):
            yaml_result = validate_yaml_syntax(config_input)
            result["yaml_validation"] = yaml_result
            
            if not yaml_result["valid"]:
                result["overall_status"] = "fail"
                result["report"] = generate_validation_report(
                    yaml_result,
                    {"valid": False, "errors": [], "warnings": []},
                )
                return result
            
            config = yaml_result["parsed_config"]
        else:
            # Already a dict
            result["yaml_validation"] = {"valid": True, "parsed_config": config_input}
            config = config_input
        
        # Phase 2: Schema validation
        print("Config Validation: Validating schema...")
        schema_result = validate_schema(config)
        result["schema_validation"] = schema_result
        
        # Phase 3: Optionally fetch sample pages
        if fetch_sample_pages and not sample_pages:
            print("Config Validation: Fetching sample pages for testing...")
            sample_pages = await self._fetch_sample_pages(config, max_pages_to_fetch)
        
        # Phase 4: Test extraction rules
        extraction_result = None
        if sample_pages:
            print(f"Config Validation: Testing extraction rules against {len(sample_pages)} pages...")
            extraction_result = check_extraction_rules(config, sample_pages)
            result["extraction_test"] = extraction_result
        
        # Phase 5: Test crawl rules
        crawl_urls = sample_urls or self._get_sample_urls_for_testing(config)
        print(f"Config Validation: Testing crawl rules against {len(crawl_urls)} URLs...")
        crawl_result = check_crawl_rules(config, crawl_urls)
        result["crawl_rule_test"] = crawl_result
        
        # Phase 6: Generate validation report
        print("Config Validation: Generating report...")
        report = generate_validation_report(
            result["yaml_validation"],
            schema_result,
            extraction_result,
            crawl_result,
        )
        result["report"] = report
        result["overall_status"] = report["overall_status"]
        
        # Phase 7: LLM analysis (if available)
        if self.use_agno:
            print("Config Validation: Running Agno LLM analysis...")
            try:
                llm_analysis = self._analyze_with_agno(config, report)
                result["llm_analysis"] = llm_analysis
            except Exception as e:
                result["llm_analysis"] = {
                    "status": "error",
                    "error": str(e),
                }
        else:
            result["llm_analysis"] = {
                "status": "disabled",
                "message": "LLM analysis not available (no API key configured)",
            }
        
        return result
    
    def validate_sync(
        self,
        config_input: str | dict,
        sample_pages: Optional[List[Dict[str, str]]] = None,
        sample_urls: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Synchronous validation without page fetching.
        
        This method performs validation without async page fetching.
        Useful for quick schema-only validation.
        
        Args:
            config_input: YAML string or parsed config dict
            sample_pages: Optional pre-fetched pages for extraction testing
            sample_urls: Optional URLs for crawl rule testing
            
        Returns:
            Validation result (same structure as validate())
        """
        result = {
            "overall_status": "validating",
        }
        
        # Phase 1: Parse YAML if string input
        if isinstance(config_input, str):
            yaml_result = validate_yaml_syntax(config_input)
            result["yaml_validation"] = yaml_result
            
            if not yaml_result["valid"]:
                result["overall_status"] = "fail"
                result["report"] = generate_validation_report(
                    yaml_result,
                    {"valid": False, "errors": [], "warnings": []},
                )
                return result
            
            config = yaml_result["parsed_config"]
        else:
            result["yaml_validation"] = {"valid": True, "parsed_config": config_input}
            config = config_input
        
        # Phase 2: Schema validation
        schema_result = validate_schema(config)
        result["schema_validation"] = schema_result
        
        # Phase 3: Test extraction rules (if pages provided)
        extraction_result = None
        if sample_pages:
            extraction_result = check_extraction_rules(config, sample_pages)
            result["extraction_test"] = extraction_result
        
        # Phase 4: Test crawl rules
        crawl_urls = sample_urls or self._get_sample_urls_for_testing(config)
        crawl_result = check_crawl_rules(config, crawl_urls)
        result["crawl_rule_test"] = crawl_result
        
        # Phase 5: Generate report
        report = generate_validation_report(
            result["yaml_validation"],
            schema_result,
            extraction_result,
            crawl_result,
        )
        result["report"] = report
        result["overall_status"] = report["overall_status"]
        
        return result
    
    async def _fetch_sample_pages(
        self,
        config: dict,
        max_pages: int,
    ) -> List[Dict[str, str]]:
        """
        Fetch sample pages from the configured domain for testing.
        
        Args:
            config: Parsed config dict
            max_pages: Maximum number of pages to fetch
            
        Returns:
            List of page dicts with 'url' and 'html_content'
        """
        sample_pages = []
        
        # Get seed URLs from config
        seed_urls = []
        for domain in config.get("domains", []):
            seed_urls.extend(domain.get("seed_urls", []))
        
        if not seed_urls:
            return sample_pages
        
        # Fetch pages
        urls_to_fetch = seed_urls[:max_pages]
        fetch_result = await self.page_fetcher.fetch_pages(urls_to_fetch)
        
        for page in fetch_result.pages:
            if page.html_content and not page.error:
                sample_pages.append({
                    "url": page.url,
                    "html_content": page.html_content,
                })
        
        return sample_pages
    
    def _get_sample_urls_for_testing(self, config: dict) -> List[str]:
        """
        Generate sample URLs for crawl rule testing.
        
        Args:
            config: Parsed config dict
            
        Returns:
            List of sample URLs to test
        """
        sample_urls = []
        
        for domain in config.get("domains", []):
            domain_url = domain.get("url", "")
            
            # Add seed URLs
            sample_urls.extend(domain.get("seed_urls", []))
            
            # Add common URL patterns for testing
            if domain_url:
                common_patterns = [
                    "/",
                    "/blog/",
                    "/blog/post-1",
                    "/products/",
                    "/products/item-123",
                    "/admin/",
                    "/login/",
                    "/cart/",
                    "/search?q=test",
                    "/api/v1/data",
                ]
                
                for pattern in common_patterns:
                    sample_urls.append(f"{domain_url}{pattern}")
        
        return list(set(sample_urls))  # Remove duplicates
    
    def _analyze_with_agno(
        self,
        config: dict,
        report: dict,
    ) -> Dict[str, Any]:
        """
        Use Agno Agent to analyze the validation results and provide recommendations.
        """
        # Prepare summary for LLM
        summary = {
            "overall_status": report.get("overall_status"),
            "error_count": len(report.get("all_errors", [])),
            "warning_count": len(report.get("all_warnings", [])),
            "errors": report.get("all_errors", [])[:5],  # First 5 errors
            "warnings": report.get("all_warnings", [])[:5],  # First 5 warnings
            "extraction_summary": report.get("extraction_rules", {}).get("summary", {}),
            "crawl_rules_summary": report.get("crawl_rules", {}),
        }
        
        # Create prompt for analysis
        prompt = f"""Analyze this Open Crawler configuration validation report and provide recommendations.

Validation Summary:
{json.dumps(summary, indent=2)}

Config being validated (YAML excerpt):
```yaml
output_sink: {config.get('output_sink', 'N/A')}
domains:
  - url: {config.get('domains', [{}])[0].get('url', 'N/A')}
    seed_urls: {config.get('domains', [{}])[0].get('seed_urls', [])[:3]}
    crawl_rules: {len(config.get('domains', [{}])[0].get('crawl_rules', []))} rules defined
    extraction_rulesets: {len(config.get('domains', [{}])[0].get('extraction_rulesets', []))} rulesets defined
```

Please provide:
1. Assessment of the configuration's readiness for crawling
2. Prioritized list of issues to fix (most critical first)
3. Specific recommendations for each error/warning
4. Any additional suggestions for improving the configuration

Format as structured feedback with clear action items."""
        
        # Get or create agent and run analysis
        agent = self._get_agno_agent()
        response = agent.run(prompt)
        
        # Extract content from response
        content = response.content if hasattr(response, 'content') else str(response)
        
        return {
            "status": "completed",
            "analysis": content,
        }
    
    def validate_yaml_only(self, yaml_content: str) -> Dict[str, Any]:
        """
        Validate only YAML syntax (quick check).
        
        Args:
            yaml_content: YAML configuration string
            
        Returns:
            YAML validation result
        """
        return validate_yaml_syntax(yaml_content)
    
    def validate_schema_only(self, config: dict) -> Dict[str, Any]:
        """
        Validate only schema structure (no live testing).
        
        Args:
            config: Parsed config dict
            
        Returns:
            Schema validation result
        """
        return validate_schema(config)
