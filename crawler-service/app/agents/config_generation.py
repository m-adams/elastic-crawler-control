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
from utils.logging import get_logger

logger = get_logger(__name__)


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
    "FIELD NAMING WITH SUFFIXES - IMPORTANT:",
    "Use suffixes to control Elasticsearch field mapping. Suggest the best suffix for each field:",
    "",
    "| Suffix      | ES Mapping Type                      | When to Use                          |",
    "|-------------|--------------------------------------|--------------------------------------|",
    "| _semantic   | text + keyword + ELSER + Jina        | Long content users search by meaning |",
    "|             |                                      | (articles, descriptions, docs)       |",
    "| _text       | text + keyword                       | Short searchable text                |",
    "|             |                                      | (titles, names, short fields)        |",
    "| _keyword    | keyword only                         | Exact match, filtering, aggregations |",
    "|             |                                      | (tags, categories, SKUs, IDs, status)|",
    "| _date       | date                                 | Date/time values                     |",
    "| _num/_count | float                                | Numbers (prices, ratings, counts)    |",
    "| (no suffix) | text + keyword                       | Default if unsure                    |",
    "",
    "Examples of good field naming:",
    "- article_body_semantic: Long article content (semantic search)",
    "- product_description_semantic: Product details users search for",
    "- article_title_text: Searchable title",
    "- author_name_text: Author names to search",
    "- category_keyword: Filter/facet by category",
    "- tags_keyword: Exact tag matching",
    "- sku_keyword: Product identifiers",
    "- publish_date: Date field (auto-detected)",
    "- product_price: Numeric (auto-detected by name)",
    "- rating_num: Explicit numeric suffix",
    "",
    "For each extraction field, include 'suggested_suffix' and 'suffix_reason' in your reasoning.",
    "",
    "Document your reasoning for:",
    "- Why specific crawl rules were chosen",
    "- Why certain extraction selectors were selected",
    "- How content type was determined",
    "- Why each field suffix was recommended (how users will search/filter)",
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
        user_context: Optional[str] = None,
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
            user_context: Free-text description of user's goals/use case for crawling
            
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
            "user_context": user_context,
        }
        
        # Phase 1: Load relevant knowledge patterns
        logger.debug("Loading knowledge patterns")
        patterns = load_knowledge_patterns("all")
        result["knowledge_patterns"] = patterns.get("key_rules", [])
        
        # Phase 2: Detect content type from analysis if not provided
        # Use user_context to help with detection if available
        if not content_type:
            content_type = self._detect_content_type(site_analysis, user_context=user_context)
            logger.info("Detected content type", domain=domain, content_type=content_type, from_user_context=bool(user_context))
        result["content_type"] = content_type
        
        # Add user_context to site_analysis so tools can access it
        enriched_site_analysis = {**site_analysis}
        if user_context:
            enriched_site_analysis["user_context"] = user_context
            logger.debug("Added user_context to site analysis for config generation")
        
        # Phase 3: Generate configuration using tools
        logger.info("Generating configuration", domain=domain, content_type=content_type, has_user_context=bool(user_context))
        
        config_result = generate_full_config(
            domain=domain,
            site_analysis=enriched_site_analysis,
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
        result["field_metadata"] = config_result.get("field_metadata", [])
        
        # Phase 3.5: Try LLM-based extraction rule generation (if HTML samples available)
        html_samples = enriched_site_analysis.get("html_samples", [])
        if self.use_agno and html_samples and not custom_fields:
            logger.info(
                "Generating LLM-based extraction rules",
                domain=domain,
                html_sample_count=len(html_samples),
                has_user_context=bool(user_context),
            )
            try:
                llm_extraction = self._generate_extraction_rules_with_llm(
                    enriched_site_analysis,
                    content_type,
                    user_context=user_context,
                )
                if llm_extraction and llm_extraction.get("extraction_rulesets"):
                    # Replace default extraction rules with LLM-generated ones
                    if result["config"].get("domains"):
                        result["config"]["domains"][0]["extraction_rulesets"] = (
                            llm_extraction["extraction_rulesets"]
                        )
                    # Regenerate YAML with new extraction rules
                    import yaml
                    result["yaml_content"] = yaml.dump(
                        result["config"],
                        default_flow_style=False,
                        sort_keys=False,
                        allow_unicode=True,
                    )
                    result["reasoning"].append("--- LLM-Generated Extraction Rules ---")
                    result["reasoning"].extend(llm_extraction.get("reasoning", []))
                    result["sample_document"] = llm_extraction.get("sample_document", {})
                    result["field_metadata"] = llm_extraction.get("field_metadata", [])
                    result["llm_extraction_used"] = True
                    logger.info("Using LLM-generated extraction rules", rule_count=len(llm_extraction["extraction_rulesets"][0]["rules"]))
                else:
                    logger.info("LLM extraction returned no rules, using defaults")
                    result["llm_extraction_used"] = False
            except Exception as e:
                logger.exception("LLM extraction failed, using defaults")
                result["llm_extraction_used"] = False
        else:
            result["llm_extraction_used"] = False
            if not html_samples:
                logger.debug("No HTML samples available for LLM extraction")
        
        # Phase 4: Add custom fields if provided (overrides LLM rules)
        if custom_fields:
            logger.debug("Adding custom fields", count=len(custom_fields))
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
        logger.debug("Validating configuration structure")
        validation = validate_config_structure(result["config"])
        result["validation"] = validation
        
        if not validation["valid"]:
            result["status"] = "error"
            result["error"] = "; ".join(validation["errors"])
            return result
        
        # Phase 6: LLM enhancement (if available)
        if self.use_agno:
            logger.info("Running Agno LLM enhancement", domain=domain)
            try:
                llm_result = self._enhance_with_agno(
                    site_analysis,
                    result["config"],
                    content_type,
                    user_context=user_context,
                )
                result["llm_reasoning"] = llm_result
                logger.debug("LLM enhancement complete", domain=domain)
            except Exception as e:
                logger.exception("LLM enhancement failed", domain=domain)
                result["llm_reasoning"] = {
                    "status": "error",
                    "error": str(e),
                }
        else:
            logger.debug("LLM enhancement disabled (no API key)")
            result["llm_reasoning"] = {
                "status": "disabled",
                "message": "LLM enhancement not available (no API key configured)",
            }
        
        result["status"] = "completed"
        return result
    
    def _detect_content_type(self, site_analysis: Dict[str, Any], user_context: Optional[str] = None) -> str:
        """
        Detect content type from site analysis and optional user context.
        
        Analyzes page structures and patterns to determine the most likely
        content type (blog, ecommerce, docs, or general).
        
        If user_context is provided, uses keywords in the user's description
        to help determine content type.
        
        Args:
            site_analysis: Site investigation results
            user_context: Optional user description of their goals/use case
        """
        # First, check user_context for explicit content type hints
        if user_context:
            user_context_lower = user_context.lower()
            
            # Check for explicit content type mentions in user context
            if any(kw in user_context_lower for kw in ["product", "products", "ecommerce", "e-commerce", "shop", "store", "catalog", "inventory", "price"]):
                logger.debug("Content type from user context: ecommerce")
                return "ecommerce"
            elif any(kw in user_context_lower for kw in ["blog", "article", "articles", "news", "post", "posts", "author"]):
                logger.debug("Content type from user context: blog")
                return "blog"
            elif any(kw in user_context_lower for kw in ["doc", "docs", "documentation", "guide", "tutorial", "api", "reference", "manual"]):
                logger.debug("Content type from user context: docs")
                return "docs"
        
        # Fall back to analyzing site structure
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
    
    def _format_html_samples_for_prompt(
        self,
        html_samples: list[dict],
        max_chars_per_sample: int = 8000,
    ) -> str:
        """
        Format multiple HTML samples for inclusion in the LLM prompt.
        
        Distributes available context space across multiple samples to give
        the LLM a broader view of the site's content pages.
        
        Args:
            html_samples: List of HTML sample dicts with url, html, full_length
            max_chars_per_sample: Maximum characters per sample
            
        Returns:
            Formatted string with multiple HTML samples
        """
        if not html_samples:
            return "No HTML samples available."
        
        sections = []
        
        for i, sample in enumerate(html_samples[:3], 1):  # Max 3 samples
            url = sample.get("url", "unknown")
            html = sample.get("html", "")[:max_chars_per_sample]
            full_length = sample.get("full_length", len(html))
            score = sample.get("extraction_score", "N/A")
            
            # Truncate indicator
            truncated = " (truncated)" if len(sample.get("html", "")) > max_chars_per_sample else ""
            
            section = f"""### Sample {i}: {url}
Content score: {score} | Full HTML: {full_length:,} chars{truncated}

```html
{html}
```
"""
            sections.append(section)
        
        return "\n".join(sections)
    
    def _generate_extraction_rules_with_llm(
        self,
        site_analysis: Dict[str, Any],
        content_type: str,
        user_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Use LLM to generate custom extraction rules based on actual HTML samples.
        
        This method sends the HTML samples, user context, and extraction guide
        to the LLM which generates tailored CSS selectors for the specific site.
        
        Args:
            site_analysis: Site investigation report with html_samples
            content_type: Detected content type (blog, ecommerce, docs, general)
            user_context: User's description of what they want to extract
            
        Returns:
            Dict with extraction_rulesets, reasoning, and sample_document
        """
        # Get HTML samples from investigation
        html_samples = site_analysis.get("html_samples", [])
        if not html_samples:
            logger.warning("No HTML samples available for LLM extraction, falling back to defaults")
            return None
        
        # Load extraction guide from knowledge base
        extraction_guide = self._load_extraction_guide()
        
        # Build the user context section
        user_context_section = ""
        if user_context:
            user_context_section = f"""
## USER'S EXTRACTION GOALS

The user described their goals as:
"{user_context}"

IMPORTANT: Generate extraction rules that capture the specific data the user wants.
Focus on fields that match their stated needs.
"""
        
        # Build page structure summary from investigation
        page_structure = site_analysis.get("page_structure_analysis", {})
        page_samples_analyzed = site_analysis.get("page_samples", [])
        
        # Prepare HTML samples section (use multiple samples for better coverage)
        # Each sample is truncated to fit context, prioritizing content pages
        html_samples_section = self._format_html_samples_for_prompt(html_samples, max_chars_per_sample=8000)
        primary_sample = html_samples[0]  # For URL reference
        
        # Create the LLM prompt
        prompt = f"""You are an expert at creating Open Crawler extraction rules. 
Analyze the provided HTML samples and generate optimal extraction rules.

{user_context_section}

## CONTENT TYPE: {content_type}

## IMPORTANT: DEFAULT FIELDS ALREADY EXTRACTED

The crawler AUTOMATICALLY extracts these - DO NOT create rules for them:
- title (from <title>) - already has semantic search
- body (main content) - already has semantic search
- headings (h1-h6) - already has semantic search
- links, meta_description, meta_keywords, url components

Only extract fields that provide ADDITIONAL value beyond these defaults!
For example: author names, publish dates, categories, tags, prices, specific content sections.

## PAGE STRUCTURE ANALYSIS

Common patterns found:
{json.dumps(page_structure, indent=2)[:2000]}

Sample page metadata:
{json.dumps(page_samples_analyzed[0] if page_samples_analyzed else {}, indent=2)[:1000]}

## EXTRACTION RULES GUIDE

{extraction_guide}

## HTML SAMPLES FROM THE SITE

The following HTML samples are from actual pages on this site, prioritized by likelihood 
of being content pages (articles, posts, etc.) rather than navigation/section pages.
Design extraction rules that work across these page types.

{html_samples_section}

## YOUR TASK

Based on the HTML samples above and the user's goals, generate extraction rules that will:
1. Extract ADDITIONAL fields beyond the defaults (title, body, headings are automatic)
2. Use CSS selectors that will work reliably across similar pages on this site
3. Follow naming conventions with proper suffixes based on VALUE TYPE:
   - _semantic: Long text for meaning-based search (descriptions, articles)
   - _text: Short searchable text (names, short fields)
   - _keyword: Exact match/filtering (tags, categories, IDs, status values)
   - _date: Date/time fields
   - _num/_price/_count: Numeric values
4. Include join_as: "string" or "array" for each rule (REQUIRED!)
   - Use "array" when extracting multiple items (tags, authors, code blocks)
   - The suffix indicates the type of VALUES, not whether it's an array

RESPOND WITH ONLY A VALID JSON OBJECT in this exact format:
{{
    "extraction_rules": [
        {{
            "field_name": "author_name_text",
            "selector": ".author, .byline",
            "join_as": "string",
            "reason": "Author name for attribution, using _text for searchable name"
        }},
        {{
            "field_name": "tags_keyword",
            "selector": ".tag, .label",
            "join_as": "array",
            "reason": "Category tags for filtering, _keyword for exact match, array for multiple"
        }},
        ...more rules...
    ],
    "reasoning": "Brief explanation of the extraction strategy based on the HTML samples analyzed",
    "content_type_confirmed": "{content_type}"
}}

Generate 4-8 extraction rules that capture ADDITIONAL valuable content beyond defaults.
Use specific CSS selectors from the actual HTML - not generic guesses."""

        try:
            # Get or create agent and run
            agent = self._get_agno_agent()
            response = agent.run(prompt)
            
            # Extract content from response
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON from response
            llm_rules = self._parse_llm_extraction_response(content)
            
            if llm_rules and llm_rules.get("extraction_rules"):
                # Convert to Open Crawler format
                clean_rules = []
                field_metadata = []
                sample_doc = {}
                reasoning = [f"LLM-generated extraction rules for {content_type} content"]
                
                if llm_rules.get("reasoning"):
                    reasoning.append(f"Strategy: {llm_rules['reasoning']}")
                
                for rule in llm_rules["extraction_rules"]:
                    field_name = rule.get("field_name", "custom_field")
                    selector = rule.get("selector", "")
                    join_as = rule.get("join_as", "string")
                    reason = rule.get("reason", "")
                    
                    if not selector:
                        continue
                    
                    # Build clean rule for YAML
                    clean_rule = {
                        "action": "extract",
                        "field_name": field_name,
                        "selector": selector,
                        "source": "html",
                        "join_as": join_as,
                    }
                    clean_rules.append(clean_rule)
                    
                    # Store metadata
                    field_metadata.append({
                        "field_name": field_name,
                        "selector": selector,
                        "join_as": join_as,
                        "llm_reason": reason,
                    })
                    
                    # Add to reasoning
                    reasoning.append(f"{field_name}: {reason}")
                    
                    # Sample document
                    sample_doc[field_name] = f"[Sample {field_name} value]"
                
                logger.info(
                    "LLM generated extraction rules",
                    rule_count=len(clean_rules),
                    content_type=content_type,
                )
                
                return {
                    "extraction_rulesets": [{"rules": clean_rules}],
                    "reasoning": reasoning,
                    "sample_document": sample_doc,
                    "field_metadata": field_metadata,
                    "llm_generated": True,
                }
            else:
                logger.warning("LLM did not return valid extraction rules")
                return None
                
        except Exception as e:
            logger.exception("LLM extraction rule generation failed")
            return None
    
    def _load_extraction_guide(self) -> str:
        """Load the extraction rules guide from knowledge base."""
        from pathlib import Path
        import os
        
        # Find knowledge base path
        kb_paths = [
            Path("/app/knowledge"),  # Docker
            Path(__file__).parent.parent.parent.parent / "knowledge",  # Dev
        ]
        
        for kb_path in kb_paths:
            guide_path = kb_path / "extraction-rules" / "extraction-basics.md"
            if guide_path.exists():
                content = guide_path.read_text()
                # Return a condensed version focusing on key rules
                # Extract the most important sections
                sections = []
                
                # Get critical rules first
                if "## Critical Rule" in content:
                    start = content.find("## Critical Rule")
                    end = content.find("## Basic Structure", start)
                    if end == -1:
                        end = start + 500
                    sections.append(content[start:end])
                
                # Get default crawler fields section
                if "### Default Crawler Fields" in content:
                    start = content.find("### Default Crawler Fields")
                    end = content.find("### Cost Consideration", start)
                    if end == -1:
                        end = start + 500
                    sections.append(content[start:end])
                
                # Get reserved fields
                if "## Reserved Field Names" in content:
                    start = content.find("## Reserved Field Names")
                    end = content.find("## Field Naming", start)
                    if end == -1:
                        end = start + 800
                    sections.append(content[start:end])
                
                # Get field naming conventions section
                if "## Field Naming Conventions" in content:
                    start = content.find("## Field Naming Conventions")
                    end = content.find("## Extraction from URL", start)
                    if end == -1:
                        end = start + 2000
                    sections.append(content[start:end])
                
                return "\n\n".join(sections) if sections else content[:3000]
        
        # Fallback - inline the essential rules
        return """
## Critical Rule: join_as is REQUIRED
Every extraction rule MUST include join_as: "string" or "array"
- join_as: "string" - Combines multiple matches into one string (joined with space)
- join_as: "array" - Keeps multiple matches as array of values

## DEFAULT FIELDS ALREADY EXTRACTED (DO NOT DUPLICATE!)
The crawler AUTOMATICALLY extracts these fields - you should NOT create extraction rules for them:
- title - Page title (from <title> tag) - already has semantic search
- body - Main page content - already has semantic search  
- headings - All h1-h6 headings - already has semantic search
- links - All links on the page
- meta_description - From meta description tag
- meta_keywords - From meta keywords tag
- url, url_host, url_path - URL components
- last_crawled_at - Crawl timestamp

ONLY extract fields that provide ADDITIONAL value beyond these defaults!

## Field Naming Suffixes (IMPORTANT)
The suffix controls Elasticsearch mapping type. Use based on the VALUE TYPE, not whether it's an array:

| Suffix | ES Mapping | When to Use |
|--------|------------|-------------|
| _semantic | text + ELSER embeddings | Long content users search by meaning (descriptions, articles) |
| _text | text + keyword | Short searchable text (author names, short descriptions) |
| _keyword | keyword only | Exact match, filtering, aggregations (tags, categories, IDs, status) |
| _date | date | Date/time values |
| _num/_count/_price/_score | float | Numeric values |
| (no suffix) | text + keyword | Default if unsure |

NOTE: Arrays are controlled by join_as, NOT by field name suffix!
- For array of keywords: field_name: "tags_keyword", join_as: "array"
- For array of text: field_name: "authors_text", join_as: "array"

## Reserved Field Names (NEVER USE as field_name)
- id, title, body, body_content, url, links, headings
- meta_description, meta_keywords, url_host, url_path

Always use prefixed names: article_title, blog_content, product_price
"""
    
    def _parse_llm_extraction_response(self, content: str) -> Optional[Dict]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        import re
        
        # Try to extract JSON from markdown code block
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # Try to find raw JSON object
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                json_str = json_match.group(0)
            else:
                return None
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse LLM extraction response", error=str(e))
            return None
    
    def _enhance_with_agno(
        self,
        site_analysis: Dict[str, Any],
        config: Dict[str, Any],
        content_type: str,
        user_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Use Agno Agent to enhance and explain the configuration.
        
        Args:
            site_analysis: Site investigation report
            config: Generated config dictionary
            content_type: Detected or specified content type
            user_context: User's goals/use case for crawling (optional)
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
        
        # Build user context section if provided
        user_context_section = ""
        if user_context:
            user_context_section = f"""
User's Goals/Use Case:
{user_context}

IMPORTANT: Evaluate the configuration against the user's stated goals above.
Ensure the crawl rules and extraction rules will capture the data they need.
"""
        
        # Create prompt for analysis
        prompt = f"""Review this Open Crawler configuration and provide your analysis.
{user_context_section}
Configuration Summary:
{json.dumps(summary, indent=2)}

Generated Configuration (YAML):
```yaml
{generate_full_config(site_analysis.get('domain', ''), site_analysis)['yaml_content']}
```

Please provide:
1. Assessment of the configuration quality{' and alignment with user goals' if user_context else ''}
2. Any potential issues or improvements
3. Explanation of why the extraction selectors chosen are appropriate
4. Suggestions for optimizing crawl efficiency
{f"5. Specific recommendations to better meet the user's stated goals" if user_context else ""}

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
