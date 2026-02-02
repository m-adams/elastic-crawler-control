"""
Config Generation Agent (Agno-powered).

Generates valid Open Crawler YAML configurations based on site investigation
reports and knowledge base patterns. Uses LLM with reasoning capture.

This module provides:
- ConfigGenerationAgent: High-level class for config generation
- create_config_generation_agent(): Factory for creating the underlying Agno agent

The agent uses the following tools:
- load_knowledge_patterns: Load patterns from the knowledge base
- generate_domain_config: Create domain configuration section
- generate_crawl_rules: Create crawl rules based on analysis
- generate_extraction_rules: Create extraction rules for content
- generate_full_config: Generate complete YAML configuration
- validate_config_structure: Validate config before use
"""

import json
from typing import Any, Dict, Optional

from agno.agent import Agent

from utils.agno_model import get_model, is_agno_available

from agents.config_generation_tools import (
    load_knowledge_patterns,
    generate_domain_config,
    generate_crawl_rules,
    generate_extraction_rules,
    generate_full_config,
    validate_config_structure,
    CONFIG_GENERATION_TOOLS,
)


# Agent instructions for LLM-powered config generation
CONFIG_GENERATION_INSTRUCTIONS = [
    "You are a Config Generation Agent that creates Open Crawler YAML configurations.",
    "Your goal is to generate valid, optimized configurations based on site investigation reports.",
    "",
    "When generating a configuration, follow these steps:",
    "1. First, load relevant knowledge patterns for the content type",
    "2. Analyze the site investigation report to understand site structure",
    "3. Generate appropriate crawl rules based on the site analysis",
    "4. Generate extraction rules matching the content type",
    "5. Combine into a full configuration with proper settings",
    "6. Validate the configuration structure",
    "",
    "CRITICAL RULES TO FOLLOW:",
    "- ALWAYS include 'join_as' on every extraction rule (string or array)",
    "- NEVER use reserved field names: id, title, body, url, links, headings",
    "- Domain URLs must NOT have trailing slashes",
    "- File output requires max_crawl_depth >= 1",
    "- Crawl rules are evaluated in order - put specific rules before broad rules",
    "",
    "Document your reasoning for:",
    "- Why specific crawl rules were chosen",
    "- Why certain extraction selectors were selected",
    "- How content type was determined",
    "- Any trade-offs or limitations",
    "",
    "Always provide:",
    "- The complete YAML configuration",
    "- Reasoning for each major decision",
    "- Validation status and any warnings",
    "- Sample document preview showing expected extracted fields",
]


def create_config_generation_agent(
    model_id: Optional[str] = None,
    debug_mode: bool = False,
) -> Agent:
    """
    Create an Agno Config Generation Agent.
    
    This factory function creates a fully configured Agno Agent for config generation.
    The agent has access to all config generation tools and uses the LLM Proxy model.
    
    Args:
        model_id: Optional override for the LLM model ID
        debug_mode: If True, enable debug output
        
    Returns:
        Configured Agno Agent instance
        
    Raises:
        ValueError: If LLM Proxy API key is not configured
        
    Example:
        >>> agent = create_config_generation_agent()
        >>> response = agent.run("Generate a config for https://example.com based on: {site_analysis}")
        >>> print(response.content)
    """
    model = get_model(model_id=model_id, temperature=0.2)  # Lower temp for more consistent configs
    
    return Agent(
        model=model,
        name="ConfigGenerationAgent",
        description="Generates Open Crawler YAML configurations based on site analysis",
        instructions=CONFIG_GENERATION_INSTRUCTIONS,
        tools=CONFIG_GENERATION_TOOLS,
        markdown=True,
        debug_mode=debug_mode,
    )


class ConfigGenerationAgent:
    """
    Agent for generating Open Crawler configurations.
    
    This class provides a high-level interface for config generation that
    takes site investigation reports as input and produces valid YAML configs.
    
    The agent can operate in two modes:
    1. LLM-powered: Uses Agno Agent for intelligent generation (when API key available)
    2. Tool-based: Uses tools directly for deterministic generation (fallback)
    
    Generates:
    - Domain configuration with seed URLs
    - Crawl rules based on site structure
    - Extraction rules for content type
    - Complete YAML configuration
    
    Example:
        >>> agent = ConfigGenerationAgent()
        >>> result = agent.generate(site_analysis_report)
        >>> print(result["yaml_content"])
    """
    
    def __init__(
        self,
        use_agno: bool = True,
        debug_mode: bool = False,
    ):
        """
        Initialize config generation agent.
        
        Args:
            use_agno: Whether to use Agno for LLM generation (default: True)
            debug_mode: Enable debug output for Agno agent
        """
        self.use_agno = use_agno and is_agno_available()
        self.debug_mode = debug_mode
        
        # Agno agent (lazy initialized)
        self._agno_agent: Optional[Agent] = None
    
    def _get_agno_agent(self) -> Agent:
        """Get or create the Agno agent instance."""
        if self._agno_agent is None:
            self._agno_agent = create_config_generation_agent(debug_mode=self.debug_mode)
        return self._agno_agent
    
    def generate(
        self,
        site_analysis: Dict[str, Any],
        output_sink: str = "file",
        output_index: Optional[str] = None,
        output_dir: str = "/config/results/output",
        content_type: Optional[str] = None,
        content_focus: Optional[str] = None,
        max_crawl_depth: int = 2,
        custom_fields: Optional[list[dict]] = None,
    ) -> Dict[str, Any]:
        """
        Generate an Open Crawler configuration from site analysis.
        
        This method orchestrates the config generation workflow using the
        underlying tools. It can operate with or without LLM enhancement.
        
        Args:
            site_analysis: Site investigation report (from SiteInvestigationAgent)
            output_sink: Output type ("console", "file", or "elasticsearch")
            output_index: Elasticsearch index name (for ES output)
            output_dir: Output directory for file output
            content_type: Content type for extraction ("blog", "ecommerce", "docs")
            content_focus: Focus area for crawl rules (e.g., "/blog/")
            max_crawl_depth: Maximum crawl depth (default: 2)
            custom_fields: Optional custom extraction fields
            
        Returns:
            Config generation result containing:
            - config: Complete config dictionary
            - yaml_content: YAML string ready for file
            - reasoning: List of generation decisions
            - validation: Validation results
            - sample_document: Example extracted document
            - llm_reasoning: LLM-generated reasoning (if Agno used)
        """
        # Extract domain from site analysis
        domain = site_analysis.get("domain", "")
        if not domain:
            return {
                "status": "error",
                "error": "No domain found in site analysis",
                "config": None,
                "yaml_content": None,
            }
        
        # Initialize result structure
        result = {
            "status": "generating",
            "domain": domain,
        }
        
        # Phase 1: Load relevant knowledge patterns
        print(f"Config Generation: Loading knowledge patterns...")
        patterns = load_knowledge_patterns("all")
        result["knowledge_patterns"] = patterns.get("key_rules", [])
        
        # Phase 2: Detect content type from analysis if not provided
        if not content_type:
            content_type = self._detect_content_type(site_analysis)
            print(f"Config Generation: Detected content type: {content_type}")
        result["content_type"] = content_type
        
        # Phase 3: Generate configuration using tools
        print(f"Config Generation: Generating configuration for {domain}...")
        
        config_result = generate_full_config(
            domain=domain,
            site_analysis=site_analysis,
            output_sink=output_sink,
            output_index=output_index,
            output_dir=output_dir,
            content_type=content_type,
            content_focus=content_focus,
            max_crawl_depth=max_crawl_depth,
        )
        
        result["config"] = config_result["config"]
        result["yaml_content"] = config_result["yaml_content"]
        result["reasoning"] = config_result["reasoning"]
        result["sample_document"] = config_result.get("sample_document", {})
        
        # Phase 4: Add custom fields if provided
        if custom_fields:
            print(f"Config Generation: Adding {len(custom_fields)} custom fields...")
            extraction_result = generate_extraction_rules(
                site_analysis,
                content_type=content_type,
                custom_fields=custom_fields,
            )
            # Update extraction rulesets in config
            if result["config"].get("domains"):
                result["config"]["domains"][0]["extraction_rulesets"] = (
                    extraction_result["extraction_rulesets"]
                )
                result["reasoning"].extend(extraction_result["reasoning"])
                result["sample_document"].update(extraction_result.get("sample_document", {}))
        
        # Phase 5: Validate configuration
        print(f"Config Generation: Validating configuration...")
        validation = validate_config_structure(result["config"])
        result["validation"] = validation
        
        if not validation["valid"]:
            result["status"] = "error"
            result["error"] = "; ".join(validation["errors"])
            return result
        
        # Phase 6: LLM enhancement (if available)
        if self.use_agno:
            print(f"Config Generation: Running Agno LLM enhancement...")
            try:
                llm_result = self._enhance_with_agno(
                    site_analysis,
                    result["config"],
                    content_type,
                )
                result["llm_reasoning"] = llm_result
            except Exception as e:
                result["llm_reasoning"] = {
                    "status": "error",
                    "error": str(e),
                }
        else:
            result["llm_reasoning"] = {
                "status": "disabled",
                "message": "LLM enhancement not available (no API key configured)",
            }
        
        result["status"] = "completed"
        return result
    
    def _detect_content_type(self, site_analysis: Dict[str, Any]) -> str:
        """
        Detect content type from site analysis.
        
        Analyzes page structures and patterns to determine the most likely
        content type (blog, ecommerce, docs, or general).
        """
        # Check page structure patterns
        page_structure = site_analysis.get("page_structure_analysis", {})
        common_tags = page_structure.get("common_content_tags", [])
        
        # Check for indicators
        tag_strings = [str(tag).lower() for tag in common_tags]
        all_tags_text = " ".join(tag_strings)
        
        # Check metadata coverage
        metadata = page_structure.get("metadata_coverage", {})
        has_author = "0%" not in str(metadata.get("has_author", "0%"))
        has_date = "0%" not in str(metadata.get("has_date", "0%"))
        
        # Check domain and URL patterns
        domain = site_analysis.get("domain", "").lower()
        
        # Detection logic
        if any(kw in all_tags_text for kw in ["product", "price", "cart", "shop"]):
            return "ecommerce"
        elif any(kw in domain for kw in ["shop", "store", "buy"]):
            return "ecommerce"
        elif any(kw in all_tags_text for kw in ["article", "post", "blog", "author"]):
            return "blog"
        elif has_author and has_date:
            return "blog"
        elif any(kw in domain for kw in ["blog", "news"]):
            return "blog"
        elif any(kw in all_tags_text for kw in ["doc", "guide", "tutorial", "api"]):
            return "docs"
        elif any(kw in domain for kw in ["docs", "documentation", "developer"]):
            return "docs"
        else:
            return "general"
    
    def _enhance_with_agno(
        self,
        site_analysis: Dict[str, Any],
        config: Dict[str, Any],
        content_type: str,
    ) -> Dict[str, Any]:
        """
        Use Agno Agent to enhance and explain the configuration.
        """
        # Prepare summary for LLM
        summary = {
            "domain": site_analysis.get("domain"),
            "content_type": content_type,
            "pages_analyzed": site_analysis.get("page_fetch_summary", {}).get("successful", 0),
            "crawl_rules_count": len(
                config.get("domains", [{}])[0].get("crawl_rules", [])
            ),
            "extraction_rules_count": sum(
                len(ruleset.get("rules", []))
                for ruleset in config.get("domains", [{}])[0].get("extraction_rulesets", [])
            ),
            "output_sink": config.get("output_sink"),
        }
        
        # Create prompt for analysis
        prompt = f"""Review this Open Crawler configuration and provide your analysis.

Configuration Summary:
{json.dumps(summary, indent=2)}

Generated Configuration (YAML):
```yaml
{generate_full_config(site_analysis.get('domain', ''), site_analysis)['yaml_content']}
```

Please provide:
1. Assessment of the configuration quality
2. Any potential issues or improvements
3. Explanation of why the extraction selectors chosen are appropriate
4. Suggestions for optimizing crawl efficiency

Format as structured feedback."""
        
        # Get or create agent and run analysis
        agent = self._get_agno_agent()
        response = agent.run(prompt)
        
        # Extract content from response
        content = response.content if hasattr(response, 'content') else str(response)
        
        return {
            "status": "completed",
            "analysis": content,
        }
    
    def generate_from_domain(
        self,
        domain: str,
        output_sink: str = "file",
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a basic configuration for a domain without site analysis.
        
        This is a simplified method for generating configs when full site
        investigation hasn't been performed. Uses default patterns.
        
        Args:
            domain: Target domain URL
            output_sink: Output type
            content_type: Content type (if known)
            
        Returns:
            Config generation result (same structure as generate())
        """
        # Create minimal site analysis
        minimal_analysis = {
            "domain": domain,
            "recommendations": {},
            "page_structure_analysis": {},
            "page_samples": [],
        }
        
        return self.generate(
            site_analysis=minimal_analysis,
            output_sink=output_sink,
            content_type=content_type,
        )
