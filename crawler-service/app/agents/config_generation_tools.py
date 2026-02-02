"""
Agno tools for config generation.

This module provides tools for generating Open Crawler YAML configurations
based on site investigation reports and knowledge base patterns.

Each tool function:
- Has a detailed docstring for LLM understanding
- Takes simple parameters and returns JSON-serializable results
- Handles errors gracefully and returns structured error responses

Usage:
    from agents.config_generation_tools import (
        load_knowledge_patterns,
        generate_domain_config,
        generate_crawl_rules,
        generate_extraction_rules,
        generate_full_config,
        CONFIG_GENERATION_TOOLS,
    )
    
    from agno.agent import Agent
    agent = Agent(
        model=model,
        tools=CONFIG_GENERATION_TOOLS,
    )
"""

import os
import yaml
from pathlib import Path
from typing import Any, Optional


# Knowledge base path (relative to workspace root)
KNOWLEDGE_BASE_PATH = Path(__file__).parents[4] / "knowledge"


def _get_knowledge_base_path() -> Path:
    """Get the path to the knowledge base directory."""
    return KNOWLEDGE_BASE_PATH


def _safe_yaml_dump(data: dict) -> str:
    """Safely dump data to YAML string."""
    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)


def _load_knowledge_file(filename: str) -> str:
    """Load a knowledge base file by name."""
    kb_path = _get_knowledge_base_path()
    
    # Search for the file in knowledge base subdirectories
    for root, dirs, files in os.walk(kb_path):
        if filename in files:
            file_path = Path(root) / filename
            return file_path.read_text()
    
    return f"File not found: {filename}"


# ============================================================================
# AGNO TOOLS
# ============================================================================


def load_knowledge_patterns(pattern_type: str) -> dict:
    """
    Load patterns from the Open Crawler knowledge base.
    
    This tool retrieves documented patterns and best practices for Open Crawler
    configuration. Use this to ensure generated configs follow established patterns.
    
    Args:
        pattern_type: Type of patterns to load. Valid values:
            - "base-config": Base configuration structure and required fields
            - "extraction-basics": Extraction rule fundamentals (join_as requirement, etc.)
            - "extraction-patterns": Common extraction patterns (dates, authors, prices)
            - "crawl-rules": Crawl rule patterns and evaluation order
            - "validation": Validation checklist and common errors
            - "all": Summary of all key patterns
    
    Returns:
        A dictionary containing:
        - pattern_type: The requested pattern type
        - content: The pattern documentation
        - key_rules: List of critical rules to remember
        - error: Error message if loading failed
    
    Example:
        patterns = load_knowledge_patterns("extraction-patterns")
        print(patterns["key_rules"])
    """
    kb_path = _get_knowledge_base_path()
    
    try:
        if pattern_type == "base-config":
            content = _load_knowledge_file("base-config.md")
            key_rules = [
                "Config format is flat (v0.4+) - no nested http/crawler sections",
                "Domain URL must NOT have trailing slash or path",
                "No environment variable substitution in YAML",
                "output_sink is required: console, file, or elasticsearch",
                "max_crawl_depth >= 1 required for file output",
            ]
            
        elif pattern_type == "extraction-basics":
            content = _load_knowledge_file("extraction-basics.md")
            key_rules = [
                "CRITICAL: join_as is REQUIRED on every extraction rule",
                "join_as values: 'array' (multiple items) or 'string' (concatenated)",
                "URL filter type 'equals' NOT supported in extraction_rulesets",
                "Use file output (not console) to debug extraction rules",
                "NEVER use reserved field names: id, title, body, url, links, headings",
            ]
            
        elif pattern_type == "extraction-patterns":
            content = _load_knowledge_file("extraction-patterns.md")
            key_rules = [
                "Use multiple fallback selectors: '.author, .byline, [rel=author]'",
                "Common patterns: time[datetime] for dates, .price for prices",
                "Blog pattern: h1 for title, .author/.byline for author, time for date",
                "E-commerce pattern: .product-title, .price, .availability, .sku",
                "Documentation pattern: h1 for title, .breadcrumb for navigation, pre code for examples",
            ]
            
        elif pattern_type == "crawl-rules":
            content = _load_knowledge_file("crawl-rules.md")
            key_rules = [
                "Rules evaluated in ORDER - first match wins",
                "Specific rules must come BEFORE broad rules",
                "Pattern types: begins, ends, contains, regex, equals",
                "Always end with 'deny .*' if you want allowlist behavior",
                "Escape backslashes in regex patterns: '\\\\d+' not '\\d+'",
            ]
            
        elif pattern_type == "validation":
            content = _load_knowledge_file("validation-checklist.md")
            key_rules = [
                "Validate before running: bin/crawler validate config.yml",
                "Test with urltest first: bin/crawler urltest config.yml URL",
                "Use console output for quick crawl tests",
                "Check for reserved field names in extraction rules",
                "Verify domain URL has no trailing slash",
            ]
            
        elif pattern_type == "all":
            content = "Summary of all critical patterns"
            key_rules = [
                # Base config
                "Config format is flat (v0.4+)",
                "Domain URL must NOT have trailing slash",
                "output_sink required: console, file, elasticsearch",
                # Extraction
                "CRITICAL: join_as REQUIRED on all extraction rules",
                "NEVER use reserved fields: id, title, body, url, links",
                # Crawl rules
                "Crawl rules evaluated in order - first match wins",
                "Specific rules before broad rules",
                # Validation
                "Always validate: bin/crawler validate config.yml",
            ]
            
        else:
            return {
                "pattern_type": pattern_type,
                "content": "",
                "key_rules": [],
                "error": f"Unknown pattern type: {pattern_type}. Valid types: base-config, extraction-basics, extraction-patterns, crawl-rules, validation, all",
            }
        
        return {
            "pattern_type": pattern_type,
            "content": content[:3000] if len(content) > 3000 else content,  # Limit for LLM context
            "key_rules": key_rules,
            "error": None,
        }
        
    except Exception as e:
        return {
            "pattern_type": pattern_type,
            "content": "",
            "key_rules": [],
            "error": f"Failed to load patterns: {str(e)}",
        }


def generate_domain_config(
    domain: str,
    seed_urls: list[str] | None = None,
) -> dict:
    """
    Generate the domain section of an Open Crawler config.
    
    This tool creates the basic domain configuration structure with proper
    formatting (no trailing slash on domain URL, seed_urls array).
    
    Args:
        domain: Target domain URL (e.g., "https://example.com")
        seed_urls: List of starting URLs. If not provided, uses domain root.
    
    Returns:
        A dictionary containing:
        - domain_config: Dict with url and seed_urls
        - yaml_snippet: YAML string for the domain section
        - reasoning: Explanation of config choices
    
    Example:
        result = generate_domain_config("https://example.com", ["/blog/", "/docs/"])
        print(result["yaml_snippet"])
    """
    # Normalize domain - remove trailing slash and path
    domain = domain.rstrip("/")
    if "://" in domain:
        parts = domain.split("/", 3)
        domain = "/".join(parts[:3])  # Keep scheme://host only
    
    # Generate seed URLs
    if not seed_urls:
        seed_urls = [f"{domain}/"]
    else:
        # Ensure seed URLs are absolute
        normalized_seeds = []
        for url in seed_urls:
            if url.startswith("/"):
                normalized_seeds.append(f"{domain}{url}")
            elif url.startswith("http"):
                normalized_seeds.append(url)
            else:
                normalized_seeds.append(f"{domain}/{url}")
        seed_urls = normalized_seeds
    
    domain_config = {
        "url": domain,
        "seed_urls": seed_urls,
    }
    
    yaml_snippet = _safe_yaml_dump({"domains": [domain_config]})
    
    reasoning = [
        f"Domain URL set to '{domain}' (no trailing slash per Open Crawler requirements)",
        f"Seed URLs: {len(seed_urls)} starting point(s) for crawling",
    ]
    
    return {
        "domain_config": domain_config,
        "yaml_snippet": yaml_snippet,
        "reasoning": reasoning,
    }


def generate_crawl_rules(
    site_analysis: dict,
    content_focus: str | None = None,
    exclude_patterns: list[str] | None = None,
) -> dict:
    """
    Generate crawl rules based on site analysis and focus area.
    
    This tool creates Open Crawler crawl rules to control which URLs are crawled.
    Rules are generated based on the site structure analysis and optional focus areas.
    
    Args:
        site_analysis: Site investigation report with recommendations
        content_focus: Optional focus area (e.g., "blog", "products", "docs")
        exclude_patterns: Optional list of URL patterns to exclude
    
    Returns:
        A dictionary containing:
        - crawl_rules: List of crawl rule dicts
        - yaml_snippet: YAML string for the crawl_rules section
        - reasoning: List explaining each rule
    
    Example:
        rules = generate_crawl_rules(site_analysis, content_focus="blog")
        print(rules["yaml_snippet"])
    """
    crawl_rules = []
    reasoning = []
    
    # Extract recommendations from site analysis
    recommendations = site_analysis.get("recommendations", {})
    crawl_rule_recommendations = recommendations.get("crawl_rules", [])
    
    # Apply robots.txt disallowed paths
    for rec in crawl_rule_recommendations:
        if rec.get("type") == "exclude_paths":
            for pattern in rec.get("patterns", []):
                crawl_rules.append({
                    "policy": "deny",
                    "type": "begins",
                    "pattern": pattern,
                })
                reasoning.append(f"Deny '{pattern}' - {rec.get('reason', 'from robots.txt')}")
    
    # Add content focus rules
    if content_focus:
        focus_patterns = {
            "blog": ["/blog/", "/posts/", "/articles/"],
            "products": ["/products/", "/shop/", "/store/"],
            "docs": ["/docs/", "/documentation/", "/guide/"],
            "news": ["/news/", "/press/", "/announcements/"],
        }
        
        patterns = focus_patterns.get(content_focus.lower(), [f"/{content_focus.lower()}/"])
        
        for pattern in patterns:
            crawl_rules.append({
                "policy": "allow",
                "type": "begins",
                "pattern": pattern,
            })
            reasoning.append(f"Allow '{pattern}' - focus on {content_focus} content")
    
    # Add explicit exclude patterns
    if exclude_patterns:
        for pattern in exclude_patterns:
            crawl_rules.append({
                "policy": "deny",
                "type": "contains",
                "pattern": pattern,
            })
            reasoning.append(f"Deny URLs containing '{pattern}' - explicit exclusion")
    
    # Common exclusions (if focus is specified, deny everything else)
    common_exclusions = [
        ("deny", "contains", "?", "Exclude URLs with query parameters"),
        ("deny", "begins", "/admin/", "Exclude admin pages"),
        ("deny", "begins", "/login/", "Exclude authentication pages"),
        ("deny", "begins", "/cart/", "Exclude shopping cart"),
        ("deny", "begins", "/checkout/", "Exclude checkout flow"),
    ]
    
    for policy, type_, pattern, reason in common_exclusions:
        # Check if already added
        exists = any(
            r.get("pattern") == pattern 
            for r in crawl_rules
        )
        if not exists:
            crawl_rules.append({
                "policy": policy,
                "type": type_,
                "pattern": pattern,
            })
            reasoning.append(f"{policy.title()} '{pattern}' - {reason}")
    
    # If content focus specified, add final deny-all
    if content_focus:
        crawl_rules.append({
            "policy": "deny",
            "type": "regex",
            "pattern": ".*",
        })
        reasoning.append("Deny all other URLs - allowlist behavior for focused crawl")
    
    yaml_snippet = _safe_yaml_dump({"crawl_rules": crawl_rules}) if crawl_rules else ""
    
    return {
        "crawl_rules": crawl_rules,
        "yaml_snippet": yaml_snippet,
        "reasoning": reasoning,
    }


def generate_extraction_rules(
    site_analysis: dict,
    content_type: str | None = None,
    custom_fields: list[dict] | None = None,
) -> dict:
    """
    Generate extraction rules based on site analysis and content type.
    
    This tool creates Open Crawler extraction rules to extract structured data
    from HTML. Rules include the REQUIRED join_as field and use prefixed field
    names to avoid reserved field conflicts.
    
    Args:
        site_analysis: Site investigation report with page structure analysis
        content_type: Type of content (e.g., "blog", "ecommerce", "docs")
        custom_fields: Optional list of custom field definitions:
            [{"field_name": "my_field", "selector": ".my-class", "join_as": "string"}]
    
    Returns:
        A dictionary containing:
        - extraction_rulesets: List of extraction ruleset dicts
        - yaml_snippet: YAML string for the extraction_rulesets section
        - reasoning: List explaining each rule
        - sample_document: Example of what extracted document might look like
    
    Example:
        rules = generate_extraction_rules(site_analysis, content_type="blog")
        print(rules["yaml_snippet"])
    """
    rules = []
    reasoning = []
    sample_doc = {}
    
    # Analyze page structures from site analysis
    page_structure = site_analysis.get("page_structure_analysis", {})
    page_samples = site_analysis.get("page_samples", [])
    
    # Determine content type from analysis if not provided
    if not content_type:
        # Try to infer from patterns
        common_tags = page_structure.get("common_content_tags", [])
        metadata_coverage = page_structure.get("metadata_coverage", {})
        
        if any("article" in str(tag).lower() for tag in common_tags):
            content_type = "blog"
        elif any("product" in str(tag).lower() for tag in common_tags):
            content_type = "ecommerce"
        else:
            content_type = "general"
    
    # Content-specific extraction patterns
    if content_type == "blog":
        rules.extend([
            {
                "action": "extract",
                "field_name": "article_title",
                "selector": "h1, article header h1, .post-title",
                "source": "html",
                "join_as": "string",
            },
            {
                "action": "extract",
                "field_name": "article_author",
                "selector": ".author, .byline, [rel='author'], a[href*='/author/']",
                "source": "html",
                "join_as": "string",
            },
            {
                "action": "extract",
                "field_name": "publish_date",
                "selector": "time[datetime], .date, .published, .post-date",
                "source": "html",
                "join_as": "string",
            },
            {
                "action": "extract",
                "field_name": "article_body",
                "selector": "article, .post-content, .entry-content, .article-body",
                "source": "html",
                "join_as": "string",
            },
            {
                "action": "extract",
                "field_name": "article_tags",
                "selector": ".tags .tag, .post-tags a, [rel='tag']",
                "source": "html",
                "join_as": "array",
            },
        ])
        reasoning.extend([
            "article_title: Extract main heading using h1 with fallbacks",
            "article_author: Multiple selectors for author attribution",
            "publish_date: HTML5 time element preferred, with class fallbacks",
            "article_body: Main content area with common class patterns",
            "article_tags: Tags as array for filtering/faceting",
        ])
        sample_doc = {
            "article_title": "Example Blog Post Title",
            "article_author": "John Doe",
            "publish_date": "2024-01-15",
            "article_body": "This is the main content...",
            "article_tags": ["technology", "ai", "tutorial"],
        }
        
    elif content_type == "ecommerce":
        rules.extend([
            {
                "action": "extract",
                "field_name": "product_name",
                "selector": ".product-title, h1.product-name, [itemprop='name']",
                "source": "html",
                "join_as": "string",
            },
            {
                "action": "extract",
                "field_name": "product_price",
                "selector": ".price, [data-price], [itemprop='price'], .product-price",
                "source": "html",
                "join_as": "string",
            },
            {
                "action": "extract",
                "field_name": "product_description",
                "selector": ".product-description, [itemprop='description'], .description",
                "source": "html",
                "join_as": "string",
            },
            {
                "action": "extract",
                "field_name": "product_sku",
                "selector": "[itemprop='sku'], .sku, .product-id",
                "source": "html",
                "join_as": "string",
            },
            {
                "action": "extract",
                "field_name": "product_availability",
                "selector": ".availability, .stock-status, [itemprop='availability']",
                "source": "html",
                "join_as": "string",
            },
            {
                "action": "extract",
                "field_name": "product_rating",
                "selector": ".rating, [itemprop='ratingValue'], .stars",
                "source": "html",
                "join_as": "string",
            },
        ])
        reasoning.extend([
            "product_name: Primary product title with schema.org fallback",
            "product_price: Multiple price selector patterns",
            "product_description: Product details for search",
            "product_sku: Unique product identifier",
            "product_availability: Stock status for filtering",
            "product_rating: Review ratings for sorting/filtering",
        ])
        sample_doc = {
            "product_name": "Example Product",
            "product_price": "$29.99",
            "product_description": "Product description text...",
            "product_sku": "SKU-12345",
            "product_availability": "In Stock",
            "product_rating": "4.5",
        }
        
    elif content_type == "docs":
        rules.extend([
            {
                "action": "extract",
                "field_name": "doc_title",
                "selector": "h1",
                "source": "html",
                "join_as": "string",
            },
            {
                "action": "extract",
                "field_name": "doc_breadcrumbs",
                "selector": ".breadcrumb li, nav.breadcrumbs a, .breadcrumb-item",
                "source": "html",
                "join_as": "array",
            },
            {
                "action": "extract",
                "field_name": "doc_sections",
                "selector": "h2, h3",
                "source": "html",
                "join_as": "array",
            },
            {
                "action": "extract",
                "field_name": "doc_content",
                "selector": "article, .content, .documentation, main",
                "source": "html",
                "join_as": "string",
            },
            {
                "action": "extract",
                "field_name": "code_examples",
                "selector": "pre code, .highlight code, .code-block",
                "source": "html",
                "join_as": "array",
            },
        ])
        reasoning.extend([
            "doc_title: Main documentation page title",
            "doc_breadcrumbs: Navigation hierarchy as array",
            "doc_sections: Section headings for TOC/navigation",
            "doc_content: Main documentation content",
            "code_examples: Code snippets as array for reference",
        ])
        sample_doc = {
            "doc_title": "Getting Started Guide",
            "doc_breadcrumbs": ["Docs", "Tutorials", "Getting Started"],
            "doc_sections": ["Installation", "Configuration", "Usage"],
            "doc_content": "Documentation content...",
            "code_examples": ["npm install ...", "const client = new Client()"],
        }
        
    else:  # general
        rules.extend([
            {
                "action": "extract",
                "field_name": "page_title",
                "selector": "h1",
                "source": "html",
                "join_as": "string",
            },
            {
                "action": "extract",
                "field_name": "page_summary",
                "selector": ".summary, .excerpt, .lead, meta[name='description']",
                "source": "html",
                "join_as": "string",
            },
            {
                "action": "extract",
                "field_name": "page_content",
                "selector": "article, main, .content, #content",
                "source": "html",
                "join_as": "string",
            },
        ])
        reasoning.extend([
            "page_title: Main heading for search results",
            "page_summary: Brief description/excerpt",
            "page_content: Main page content for full-text search",
        ])
        sample_doc = {
            "page_title": "Page Title",
            "page_summary": "Brief page summary...",
            "page_content": "Main content...",
        }
    
    # Add custom fields if provided
    if custom_fields:
        for field in custom_fields:
            # Ensure join_as is present
            if "join_as" not in field:
                field["join_as"] = "string"
            if "action" not in field:
                field["action"] = "extract"
            if "source" not in field:
                field["source"] = "html"
            
            rules.append(field)
            reasoning.append(f"{field.get('field_name', 'custom')}: Custom field extraction")
            sample_doc[field.get("field_name", "custom_field")] = "Custom value"
    
    # Build extraction ruleset
    extraction_rulesets = [{"rules": rules}]
    
    yaml_snippet = _safe_yaml_dump({"extraction_rulesets": extraction_rulesets})
    
    return {
        "extraction_rulesets": extraction_rulesets,
        "yaml_snippet": yaml_snippet,
        "reasoning": reasoning,
        "sample_document": sample_doc,
        "content_type_detected": content_type,
    }


def generate_full_config(
    domain: str,
    site_analysis: dict,
    output_sink: str = "file",
    output_index: str | None = None,
    output_dir: str = "/config/results/output",
    content_type: str | None = None,
    content_focus: str | None = None,
    max_crawl_depth: int = 2,
    user_agent: str = "OpenCrawlerConfigGenerator/1.0",
) -> dict:
    """
    Generate a complete Open Crawler YAML configuration.
    
    This tool combines all configuration sections into a valid Open Crawler
    config file. It applies knowledge base patterns and best practices.
    
    Args:
        domain: Target domain URL
        site_analysis: Site investigation report
        output_sink: Output type ("console", "file", or "elasticsearch")
        output_index: Elasticsearch index name (required for ES output)
        output_dir: Output directory for file output (container path)
        content_type: Content type for extraction rules ("blog", "ecommerce", "docs")
        content_focus: Focus area for crawl rules (limits to specific sections)
        max_crawl_depth: Maximum crawl depth (default: 2, minimum 1 for file output)
        user_agent: Custom user agent string
    
    Returns:
        A dictionary containing:
        - config: Complete config dict
        - yaml_content: YAML string ready to save to file
        - reasoning: Complete reasoning log for all decisions
        - validation_notes: Important notes for config validation
    
    Example:
        result = generate_full_config(
            domain="https://example.com",
            site_analysis=investigation_report,
            output_sink="elasticsearch",
            output_index="my-content",
        )
        print(result["yaml_content"])
    """
    config = {}
    reasoning = []
    validation_notes = []
    
    # 1. Output configuration
    config["output_sink"] = output_sink
    reasoning.append(f"Output sink: {output_sink}")
    
    if output_sink == "elasticsearch":
        if not output_index:
            output_index = domain.replace("https://", "").replace("http://", "").replace(".", "-").replace("/", "")
        config["output_index"] = output_index
        reasoning.append(f"Elasticsearch index: {output_index}")
        validation_notes.append("Elasticsearch connection settings needed in elasticsearch: section")
        
    elif output_sink == "file":
        config["output_dir"] = output_dir
        reasoning.append(f"File output directory: {output_dir}")
        validation_notes.append("File output requires max_crawl_depth >= 1")
        if max_crawl_depth < 1:
            max_crawl_depth = 1
            reasoning.append("Adjusted max_crawl_depth to 1 (required for file output)")
    
    # 2. Basic settings
    config["max_crawl_depth"] = max_crawl_depth
    config["user_agent"] = user_agent
    config["log_level"] = "info"
    reasoning.append(f"Max crawl depth: {max_crawl_depth}")
    reasoning.append(f"User agent: {user_agent}")
    
    # 3. Domain configuration
    domain_result = generate_domain_config(domain)
    reasoning.extend(domain_result["reasoning"])
    
    # 4. Crawl rules
    crawl_result = generate_crawl_rules(site_analysis, content_focus=content_focus)
    reasoning.extend(crawl_result["reasoning"])
    
    # 5. Extraction rules
    extraction_result = generate_extraction_rules(site_analysis, content_type=content_type)
    reasoning.extend(extraction_result["reasoning"])
    
    # 6. Combine domain config with rules
    domain_config = domain_result["domain_config"]
    
    if crawl_result["crawl_rules"]:
        domain_config["crawl_rules"] = crawl_result["crawl_rules"]
    
    if extraction_result["extraction_rulesets"]:
        domain_config["extraction_rulesets"] = extraction_result["extraction_rulesets"]
    
    config["domains"] = [domain_config]
    
    # 7. Add validation notes
    validation_notes.extend([
        "Validate before running: docker compose run --rm crawler bin/crawler validate /config/your-config.yml",
        "Test with single URL first: bin/crawler urltest /config/your-config.yml <url>",
        "All extraction rules include join_as (REQUIRED)",
        "Field names are prefixed to avoid reserved field conflicts",
    ])
    
    # Generate YAML
    yaml_content = _safe_yaml_dump(config)
    
    return {
        "config": config,
        "yaml_content": yaml_content,
        "reasoning": reasoning,
        "validation_notes": validation_notes,
        "sample_document": extraction_result.get("sample_document", {}),
    }


def validate_config_structure(config: dict) -> dict:
    """
    Validate basic structure of an Open Crawler config.
    
    This tool performs basic validation checks on a config dict to catch
    common errors before running the crawler. It does NOT replace the
    official crawler validation command.
    
    Args:
        config: Config dictionary to validate
    
    Returns:
        A dictionary containing:
        - valid: Boolean indicating if basic structure is valid
        - errors: List of error messages
        - warnings: List of warning messages
        - suggestions: List of improvement suggestions
    
    Example:
        result = validate_config_structure(config)
        if not result["valid"]:
            print("Errors:", result["errors"])
    """
    errors = []
    warnings = []
    suggestions = []
    
    # Check required fields
    if "output_sink" not in config:
        errors.append("Missing required field: output_sink")
    elif config["output_sink"] not in ["console", "file", "elasticsearch"]:
        errors.append(f"Invalid output_sink: {config['output_sink']}. Must be console, file, or elasticsearch")
    
    if "domains" not in config:
        errors.append("Missing required field: domains")
    elif not isinstance(config["domains"], list) or len(config["domains"]) == 0:
        errors.append("domains must be a non-empty list")
    else:
        for i, domain in enumerate(config["domains"]):
            domain_url = domain.get("url", "")
            
            # Check domain URL format
            if not domain_url:
                errors.append(f"Domain {i}: missing url field")
            elif domain_url.endswith("/"):
                errors.append(f"Domain {i}: URL must not have trailing slash: {domain_url}")
            
            # Check seed_urls
            if "seed_urls" not in domain or not domain["seed_urls"]:
                warnings.append(f"Domain {i}: No seed_urls specified, crawler may not find pages")
            
            # Check extraction rules for join_as
            for j, ruleset in enumerate(domain.get("extraction_rulesets", [])):
                for k, rule in enumerate(ruleset.get("rules", [])):
                    if rule.get("action") == "extract" and "join_as" not in rule:
                        errors.append(
                            f"Domain {i}, ruleset {j}, rule {k}: "
                            f"Missing required field 'join_as' for extraction rule"
                        )
                    
                    # Check for reserved field names
                    field_name = rule.get("field_name", "")
                    reserved = ["id", "title", "body", "body_content", "url", "url_host", 
                               "url_path", "links", "headings", "meta_description"]
                    if field_name in reserved:
                        warnings.append(
                            f"Domain {i}, ruleset {j}, rule {k}: "
                            f"Field name '{field_name}' is reserved. Use prefixed name instead."
                        )
    
    # Check output-specific requirements
    if config.get("output_sink") == "file":
        if config.get("max_crawl_depth", 2) < 1:
            errors.append("File output requires max_crawl_depth >= 1")
        if "output_dir" not in config:
            warnings.append("File output without output_dir - will use default location")
    
    if config.get("output_sink") == "elasticsearch":
        if "output_index" not in config:
            warnings.append("Elasticsearch output without output_index specified")
        if "elasticsearch" not in config:
            suggestions.append("Add elasticsearch: section with host, port, and api_key")
    
    # General suggestions
    if config.get("log_level") != "debug":
        suggestions.append("Set log_level: debug for troubleshooting")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "suggestions": suggestions,
    }


# List of all tools for easy import
CONFIG_GENERATION_TOOLS = [
    load_knowledge_patterns,
    generate_domain_config,
    generate_crawl_rules,
    generate_extraction_rules,
    generate_full_config,
    validate_config_structure,
]
