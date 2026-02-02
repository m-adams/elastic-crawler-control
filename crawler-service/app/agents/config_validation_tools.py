"""
Agno tools for config validation.

This module provides tools for validating Open Crawler YAML configurations
through schema checks, live page testing, and crawl rule verification.

Each tool function:
- Has a detailed docstring for LLM understanding
- Takes simple parameters and returns JSON-serializable results
- Handles errors gracefully and returns structured error responses

Usage:
    from agents.config_validation_tools import (
        validate_yaml_syntax,
        validate_schema,
        test_extraction_rules,
        test_crawl_rules,
        generate_validation_report,
        CONFIG_VALIDATION_TOOLS,
    )
    
    from agno.agent import Agent
    agent = Agent(
        model=model,
        tools=CONFIG_VALIDATION_TOOLS,
    )
"""

import asyncio
import re
import yaml
from dataclasses import dataclass
from typing import Any, Optional

from bs4 import BeautifulSoup


# ============================================================================
# HELPER CLASSES AND FUNCTIONS
# ============================================================================


@dataclass
class ExtractionTestResult:
    """Result of testing an extraction rule against a page."""
    
    url: str
    field_name: str
    selector: str
    matched: bool
    match_count: int
    sample_value: Optional[str] = None
    error: Optional[str] = None


@dataclass
class CrawlRuleTestResult:
    """Result of testing a crawl rule against a URL."""
    
    url: str
    rule_index: int
    rule_pattern: str
    rule_policy: str
    matched: bool


def _apply_css_selector(html_content: str, selector: str) -> list[str]:
    """
    Apply a CSS selector to HTML content and return matched text.
    
    Args:
        html_content: Raw HTML string
        selector: CSS selector string
        
    Returns:
        List of matched text values
    """
    try:
        soup = BeautifulSoup(html_content, "lxml")
        elements = soup.select(selector)
        return [elem.get_text(strip=True) for elem in elements if elem.get_text(strip=True)]
    except Exception:
        return []


def _pattern_matches_url(pattern: str, pattern_type: str, url: str) -> bool:
    """
    Check if a crawl rule pattern matches a URL.
    
    Args:
        pattern: Pattern string
        pattern_type: Type of pattern (begins, ends, contains, regex, equals)
        url: URL to test
        
    Returns:
        True if pattern matches URL
    """
    # Extract path and query from URL for matching
    from urllib.parse import urlparse
    parsed = urlparse(url)
    path = parsed.path or "/"
    
    # Include query string for contains checks (e.g., "?" in URL)
    full_path = path
    if parsed.query:
        full_path = f"{path}?{parsed.query}"
    
    if pattern_type == "begins":
        return path.startswith(pattern)
    elif pattern_type == "ends":
        return path.endswith(pattern)
    elif pattern_type == "contains":
        return pattern in full_path
    elif pattern_type == "regex":
        try:
            return bool(re.search(pattern, path))
        except re.error:
            return False
    elif pattern_type == "equals":
        return path == pattern
    else:
        return False


# ============================================================================
# AGNO TOOLS
# ============================================================================


def validate_yaml_syntax(yaml_content: str) -> dict:
    """
    Validate YAML syntax of a configuration string.
    
    This tool parses YAML content and checks for syntax errors. It does NOT
    validate the schema or semantics of the configuration - use validate_schema
    for that.
    
    Args:
        yaml_content: YAML configuration as a string
    
    Returns:
        A dictionary containing:
        - valid: Boolean indicating if YAML syntax is valid
        - parsed_config: The parsed config dict (if valid)
        - error: Error message (if invalid)
        - line_number: Line number where error occurred (if applicable)
    
    Example:
        result = validate_yaml_syntax("output_sink: console\\ndomains: []")
        if result["valid"]:
            config = result["parsed_config"]
    """
    try:
        parsed = yaml.safe_load(yaml_content)
        
        # Check that it's a dict (not None or scalar)
        if not isinstance(parsed, dict):
            return {
                "valid": False,
                "parsed_config": None,
                "error": f"Config must be a dictionary, got {type(parsed).__name__}",
                "line_number": None,
            }
        
        return {
            "valid": True,
            "parsed_config": parsed,
            "error": None,
            "line_number": None,
        }
        
    except yaml.YAMLError as e:
        error_msg = str(e)
        line_number = None
        
        # Try to extract line number from error
        if hasattr(e, "problem_mark") and e.problem_mark:
            line_number = e.problem_mark.line + 1
        
        return {
            "valid": False,
            "parsed_config": None,
            "error": error_msg,
            "line_number": line_number,
        }


def validate_schema(config: dict) -> dict:
    """
    Validate a config against the Open Crawler schema requirements.
    
    This tool performs comprehensive schema validation including:
    - Required fields (output_sink, domains)
    - Valid field values and types
    - Crawl rule structure
    - Extraction rule requirements (join_as, field names)
    - Output-specific requirements
    
    Args:
        config: Config dictionary to validate (parsed YAML)
    
    Returns:
        A dictionary containing:
        - valid: Boolean indicating if schema is valid
        - errors: List of error messages (blocking issues)
        - warnings: List of warning messages (non-blocking)
        - field_coverage: Dict showing which fields are present
    
    Example:
        result = validate_schema(config)
        if not result["valid"]:
            print("Errors:", result["errors"])
    """
    errors = []
    warnings = []
    field_coverage = {
        "output_sink": False,
        "domains": False,
        "seed_urls": False,
        "crawl_rules": False,
        "extraction_rulesets": False,
    }
    
    # Check required top-level fields
    if "output_sink" not in config:
        errors.append("Missing required field: output_sink")
    else:
        field_coverage["output_sink"] = True
        valid_sinks = ["console", "file", "elasticsearch"]
        if config["output_sink"] not in valid_sinks:
            errors.append(f"Invalid output_sink: {config['output_sink']}. Must be one of: {valid_sinks}")
    
    # Check domains
    if "domains" not in config:
        errors.append("Missing required field: domains")
    elif not isinstance(config["domains"], list):
        errors.append("domains must be a list")
    elif len(config["domains"]) == 0:
        errors.append("domains list cannot be empty")
    else:
        field_coverage["domains"] = True
        
        # Validate each domain
        for i, domain in enumerate(config["domains"]):
            domain_errors, domain_warnings, domain_fields = _validate_domain(domain, i)
            errors.extend(domain_errors)
            warnings.extend(domain_warnings)
            
            # Update field coverage
            if domain_fields.get("seed_urls"):
                field_coverage["seed_urls"] = True
            if domain_fields.get("crawl_rules"):
                field_coverage["crawl_rules"] = True
            if domain_fields.get("extraction_rulesets"):
                field_coverage["extraction_rulesets"] = True
    
    # Check output-specific requirements
    if config.get("output_sink") == "file":
        max_depth = config.get("max_crawl_depth", 2)
        if max_depth < 1:
            errors.append("File output requires max_crawl_depth >= 1")
        if "output_dir" not in config:
            warnings.append("File output without output_dir - will use default location")
    
    if config.get("output_sink") == "elasticsearch":
        if "output_index" not in config:
            warnings.append("Elasticsearch output without output_index specified")
        if "elasticsearch" not in config:
            warnings.append("Elasticsearch output without elasticsearch connection config")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "field_coverage": field_coverage,
    }


def _validate_domain(domain: dict, index: int) -> tuple[list, list, dict]:
    """Validate a single domain configuration."""
    errors = []
    warnings = []
    fields = {"seed_urls": False, "crawl_rules": False, "extraction_rulesets": False}
    
    prefix = f"Domain {index}"
    
    # Check URL
    domain_url = domain.get("url", "")
    if not domain_url:
        errors.append(f"{prefix}: Missing required field 'url'")
    elif domain_url.endswith("/"):
        errors.append(f"{prefix}: Domain URL must NOT have trailing slash: {domain_url}")
    elif not domain_url.startswith(("http://", "https://")):
        warnings.append(f"{prefix}: Domain URL should start with http:// or https://")
    
    # Check seed_urls
    seed_urls = domain.get("seed_urls", [])
    if not seed_urls:
        warnings.append(f"{prefix}: No seed_urls specified, crawler may not find pages")
    else:
        fields["seed_urls"] = True
        for j, seed in enumerate(seed_urls):
            if not isinstance(seed, str):
                errors.append(f"{prefix}: seed_urls[{j}] must be a string")
    
    # Validate crawl_rules
    crawl_rules = domain.get("crawl_rules", [])
    if crawl_rules:
        fields["crawl_rules"] = True
        for j, rule in enumerate(crawl_rules):
            rule_errors = _validate_crawl_rule(rule, f"{prefix} crawl_rule[{j}]")
            errors.extend(rule_errors)
    
    # Validate extraction_rulesets
    extraction_rulesets = domain.get("extraction_rulesets", [])
    if extraction_rulesets:
        fields["extraction_rulesets"] = True
        for j, ruleset in enumerate(extraction_rulesets):
            rs_errors, rs_warnings = _validate_extraction_ruleset(
                ruleset, f"{prefix} extraction_ruleset[{j}]"
            )
            errors.extend(rs_errors)
            warnings.extend(rs_warnings)
    
    return errors, warnings, fields


def _validate_crawl_rule(rule: dict, prefix: str) -> list:
    """Validate a single crawl rule."""
    errors = []
    
    if "policy" not in rule:
        errors.append(f"{prefix}: Missing required field 'policy'")
    elif rule["policy"] not in ["allow", "deny"]:
        errors.append(f"{prefix}: policy must be 'allow' or 'deny', got '{rule['policy']}'")
    
    if "type" not in rule:
        errors.append(f"{prefix}: Missing required field 'type'")
    elif rule["type"] not in ["begins", "ends", "contains", "regex", "equals"]:
        errors.append(f"{prefix}: Invalid type '{rule['type']}'. Must be: begins, ends, contains, regex, equals")
    
    if "pattern" not in rule:
        errors.append(f"{prefix}: Missing required field 'pattern'")
    elif rule.get("type") == "regex":
        # Validate regex pattern
        try:
            re.compile(rule["pattern"])
        except re.error as e:
            errors.append(f"{prefix}: Invalid regex pattern '{rule['pattern']}': {e}")
    
    return errors


def _validate_extraction_ruleset(ruleset: dict, prefix: str) -> tuple[list, list]:
    """Validate an extraction ruleset."""
    errors = []
    warnings = []
    
    reserved_fields = [
        "id", "title", "body", "body_content", "url", "url_host",
        "url_path", "links", "headings", "meta_description"
    ]
    
    rules = ruleset.get("rules", [])
    if not rules:
        warnings.append(f"{prefix}: No rules defined")
        return errors, warnings
    
    for k, rule in enumerate(rules):
        rule_prefix = f"{prefix} rule[{k}]"
        
        # Check action
        action = rule.get("action", "extract")
        if action not in ["extract", "set"]:
            errors.append(f"{rule_prefix}: Invalid action '{action}'")
        
        # Check join_as for extract actions
        if action == "extract":
            if "join_as" not in rule:
                errors.append(f"{rule_prefix}: Missing REQUIRED field 'join_as' for extraction rule")
            elif rule["join_as"] not in ["string", "array"]:
                errors.append(f"{rule_prefix}: join_as must be 'string' or 'array', got '{rule['join_as']}'")
        
        # Check field_name
        field_name = rule.get("field_name", "")
        if not field_name:
            errors.append(f"{rule_prefix}: Missing required field 'field_name'")
        elif field_name in reserved_fields:
            warnings.append(f"{rule_prefix}: Field name '{field_name}' is reserved. Use a prefixed name instead.")
        
        # Check selector for extract actions
        if action == "extract" and "selector" not in rule:
            errors.append(f"{rule_prefix}: Missing required field 'selector' for extract action")
    
    return errors, warnings


def check_extraction_rules(
    config: dict,
    sample_pages: list[dict],
) -> dict:
    """
    Test extraction rules against sample pages.
    
    This tool applies the CSS selectors from extraction rules to sample pages
    and reports which selectors successfully match content. This helps verify
    that extraction rules will work on the target site.
    
    Args:
        config: Parsed config dictionary containing extraction_rulesets
        sample_pages: List of page dicts with keys:
            - url: Page URL
            - html_content: Raw HTML content of the page
    
    Returns:
        A dictionary containing:
        - total_pages: Number of pages tested
        - total_rules: Number of extraction rules tested
        - results_by_field: Dict mapping field_name to per-page results
        - summary: Overall extraction success rates
        - issues: List of identified issues
    
    Example:
        sample_pages = [{"url": "https://example.com", "html_content": "<html>..."}]
        result = test_extraction_rules(config, sample_pages)
        print(result["summary"])
    """
    results_by_field = {}
    issues = []
    
    # Get extraction rules from config
    extraction_rules = []
    for domain in config.get("domains", []):
        for ruleset in domain.get("extraction_rulesets", []):
            for rule in ruleset.get("rules", []):
                if rule.get("action", "extract") == "extract":
                    extraction_rules.append(rule)
    
    if not extraction_rules:
        return {
            "total_pages": len(sample_pages),
            "total_rules": 0,
            "results_by_field": {},
            "summary": {"message": "No extraction rules found in config"},
            "issues": ["No extraction rules defined"],
        }
    
    if not sample_pages:
        return {
            "total_pages": 0,
            "total_rules": len(extraction_rules),
            "results_by_field": {},
            "summary": {"message": "No sample pages provided for testing"},
            "issues": ["No sample pages provided"],
        }
    
    # Test each extraction rule against each page
    for rule in extraction_rules:
        field_name = rule.get("field_name", "unknown")
        selector = rule.get("selector", "")
        
        results_by_field[field_name] = {
            "selector": selector,
            "pages_tested": len(sample_pages),
            "pages_matched": 0,
            "page_results": [],
        }
        
        for page in sample_pages:
            url = page.get("url", "unknown")
            html = page.get("html_content", "")
            
            if not html:
                results_by_field[field_name]["page_results"].append({
                    "url": url,
                    "matched": False,
                    "match_count": 0,
                    "sample_value": None,
                    "error": "No HTML content available",
                })
                continue
            
            # Apply selector
            matched_values = _apply_css_selector(html, selector)
            matched = len(matched_values) > 0
            
            if matched:
                results_by_field[field_name]["pages_matched"] += 1
            
            results_by_field[field_name]["page_results"].append({
                "url": url,
                "matched": matched,
                "match_count": len(matched_values),
                "sample_value": matched_values[0][:200] if matched_values else None,
                "error": None,
            })
    
    # Generate summary
    total_fields = len(results_by_field)
    fields_with_matches = sum(
        1 for f in results_by_field.values() if f["pages_matched"] > 0
    )
    
    # Identify issues
    for field_name, data in results_by_field.items():
        match_rate = data["pages_matched"] / data["pages_tested"] if data["pages_tested"] > 0 else 0
        
        if match_rate == 0:
            issues.append(f"Field '{field_name}' (selector: {data['selector']}) matched 0 pages")
        elif match_rate < 0.5:
            issues.append(
                f"Field '{field_name}' has low match rate: "
                f"{data['pages_matched']}/{data['pages_tested']} pages ({match_rate*100:.0f}%)"
            )
    
    summary = {
        "total_fields": total_fields,
        "fields_with_matches": fields_with_matches,
        "fields_without_matches": total_fields - fields_with_matches,
        "extraction_success_rate": f"{fields_with_matches/total_fields*100:.1f}%" if total_fields > 0 else "N/A",
    }
    
    return {
        "total_pages": len(sample_pages),
        "total_rules": len(extraction_rules),
        "results_by_field": results_by_field,
        "summary": summary,
        "issues": issues,
    }


def check_crawl_rules(
    config: dict,
    sample_urls: list[str],
) -> dict:
    """
    Test crawl rules against sample URLs to verify rule logic.
    
    This tool evaluates crawl rules against sample URLs to check:
    - Which URLs would be allowed/denied
    - If there are contradictory rules
    - If seed URLs are properly allowed
    - If rule order is logical
    
    Args:
        config: Parsed config dictionary containing crawl_rules
        sample_urls: List of URLs to test against rules
    
    Returns:
        A dictionary containing:
        - total_urls: Number of URLs tested
        - total_rules: Number of crawl rules
        - allowed_urls: List of URLs that would be allowed
        - denied_urls: List of URLs that would be denied
        - url_results: Detailed results for each URL
        - issues: List of identified issues with rules
    
    Example:
        sample_urls = ["/blog/post-1", "/admin/", "/products/item"]
        result = test_crawl_rules(config, sample_urls)
        print(f"Allowed: {len(result['allowed_urls'])}")
    """
    # Get crawl rules and seed URLs from config
    crawl_rules = []
    seed_urls = []
    domain_url = ""
    
    for domain in config.get("domains", []):
        domain_url = domain.get("url", "")
        crawl_rules.extend(domain.get("crawl_rules", []))
        seed_urls.extend(domain.get("seed_urls", []))
    
    allowed_urls = []
    denied_urls = []
    url_results = []
    issues = []
    
    if not crawl_rules:
        # No rules means everything is allowed
        return {
            "total_urls": len(sample_urls),
            "total_rules": 0,
            "allowed_urls": sample_urls,
            "denied_urls": [],
            "url_results": [{"url": u, "policy": "allow", "reason": "no rules defined"} for u in sample_urls],
            "issues": ["No crawl rules defined - all URLs will be crawled"],
        }
    
    # Test each URL against rules
    for url in sample_urls:
        # Rules are evaluated in order - first match wins
        matched_rule = None
        matched_index = None
        
        for i, rule in enumerate(crawl_rules):
            pattern = rule.get("pattern", "")
            pattern_type = rule.get("type", "contains")
            
            if _pattern_matches_url(pattern, pattern_type, url):
                matched_rule = rule
                matched_index = i
                break
        
        if matched_rule:
            policy = matched_rule.get("policy", "allow")
            if policy == "allow":
                allowed_urls.append(url)
            else:
                denied_urls.append(url)
            
            url_results.append({
                "url": url,
                "policy": policy,
                "matched_rule_index": matched_index,
                "matched_pattern": matched_rule.get("pattern"),
                "matched_type": matched_rule.get("type"),
            })
        else:
            # No rule matched - default is allow (unless there's a deny-all at the end)
            allowed_urls.append(url)
            url_results.append({
                "url": url,
                "policy": "allow",
                "reason": "no rule matched - default allow",
            })
    
    # Check if seed URLs are allowed
    for seed in seed_urls:
        seed_matched_rule = None
        for i, rule in enumerate(crawl_rules):
            pattern = rule.get("pattern", "")
            pattern_type = rule.get("type", "contains")
            
            if _pattern_matches_url(pattern, pattern_type, seed):
                seed_matched_rule = rule
                if rule.get("policy") == "deny":
                    issues.append(f"Seed URL '{seed}' would be DENIED by rule: {rule}")
                break
    
    # Check for rule order issues
    allow_indices = [i for i, r in enumerate(crawl_rules) if r.get("policy") == "allow"]
    deny_indices = [i for i, r in enumerate(crawl_rules) if r.get("policy") == "deny"]
    
    # Check if there's a broad deny before specific allows
    for deny_idx in deny_indices:
        deny_rule = crawl_rules[deny_idx]
        if deny_rule.get("pattern") == ".*" or deny_rule.get("type") == "regex" and ".*" in deny_rule.get("pattern", ""):
            for allow_idx in allow_indices:
                if allow_idx > deny_idx:
                    issues.append(
                        f"Allow rule at index {allow_idx} comes AFTER deny-all rule at index {deny_idx}. "
                        f"It will never be reached."
                    )
    
    return {
        "total_urls": len(sample_urls),
        "total_rules": len(crawl_rules),
        "allowed_urls": allowed_urls,
        "denied_urls": denied_urls,
        "url_results": url_results,
        "issues": issues,
    }


def generate_validation_report(
    yaml_validation: dict,
    schema_validation: dict,
    extraction_test: dict | None = None,
    crawl_rule_test: dict | None = None,
) -> dict:
    """
    Generate a comprehensive validation report from all validation results.
    
    This tool combines results from all validation steps into a single
    structured report with an overall pass/fail status.
    
    Args:
        yaml_validation: Result from validate_yaml_syntax
        schema_validation: Result from validate_schema
        extraction_test: Optional result from test_extraction_rules
        crawl_rule_test: Optional result from test_crawl_rules
    
    Returns:
        A dictionary containing:
        - overall_status: "pass", "fail", or "warning"
        - yaml_syntax: YAML validation summary
        - schema: Schema validation summary
        - extraction_rules: Extraction test summary (if provided)
        - crawl_rules: Crawl rule test summary (if provided)
        - all_errors: Aggregated list of all errors
        - all_warnings: Aggregated list of all warnings
        - recommendations: List of recommendations for fixing issues
    
    Example:
        report = generate_validation_report(yaml_result, schema_result, extraction_result)
        if report["overall_status"] == "fail":
            print("Fix these errors:", report["all_errors"])
    """
    all_errors = []
    all_warnings = []
    recommendations = []
    
    # Process YAML validation
    yaml_summary = {
        "valid": yaml_validation.get("valid", False),
    }
    
    if not yaml_validation.get("valid"):
        yaml_error = yaml_validation.get("error", "Unknown YAML error")
        all_errors.append(f"YAML syntax error: {yaml_error}")
        
        if yaml_validation.get("line_number"):
            recommendations.append(f"Check YAML syntax at line {yaml_validation['line_number']}")
        else:
            recommendations.append("Validate YAML syntax with a YAML linter")
    
    # Process schema validation
    schema_summary = {
        "valid": schema_validation.get("valid", False),
        "error_count": len(schema_validation.get("errors", [])),
        "warning_count": len(schema_validation.get("warnings", [])),
        "field_coverage": schema_validation.get("field_coverage", {}),
    }
    
    for error in schema_validation.get("errors", []):
        all_errors.append(f"Schema error: {error}")
    
    for warning in schema_validation.get("warnings", []):
        all_warnings.append(f"Schema warning: {warning}")
    
    # Add recommendations for schema errors
    if schema_validation.get("errors"):
        if any("output_sink" in e for e in schema_validation["errors"]):
            recommendations.append("Add 'output_sink: console' (or 'file' or 'elasticsearch')")
        if any("join_as" in e for e in schema_validation["errors"]):
            recommendations.append("Add 'join_as: string' or 'join_as: array' to ALL extraction rules")
        if any("trailing slash" in e for e in schema_validation["errors"]):
            recommendations.append("Remove trailing slash from domain URL")
    
    # Process extraction test results
    extraction_summary = None
    if extraction_test:
        extraction_summary = {
            "tested": True,
            "total_pages": extraction_test.get("total_pages", 0),
            "total_rules": extraction_test.get("total_rules", 0),
            "summary": extraction_test.get("summary", {}),
        }
        
        for issue in extraction_test.get("issues", []):
            all_warnings.append(f"Extraction: {issue}")
        
        # Recommend fixing selectors that don't match
        if extraction_test.get("issues"):
            recommendations.append("Review extraction selectors that have low match rates")
    
    # Process crawl rule test results
    crawl_rule_summary = None
    if crawl_rule_test:
        crawl_rule_summary = {
            "tested": True,
            "total_urls": crawl_rule_test.get("total_urls", 0),
            "total_rules": crawl_rule_test.get("total_rules", 0),
            "allowed_count": len(crawl_rule_test.get("allowed_urls", [])),
            "denied_count": len(crawl_rule_test.get("denied_urls", [])),
        }
        
        for issue in crawl_rule_test.get("issues", []):
            if "DENIED" in issue and "Seed URL" in issue:
                all_errors.append(f"Crawl rule: {issue}")
            else:
                all_warnings.append(f"Crawl rule: {issue}")
        
        if any("Seed URL" in i for i in crawl_rule_test.get("issues", [])):
            recommendations.append("Ensure seed URLs are allowed by crawl rules")
    
    # Determine overall status
    if all_errors:
        overall_status = "fail"
    elif all_warnings:
        overall_status = "warning"
    else:
        overall_status = "pass"
    
    return {
        "overall_status": overall_status,
        "yaml_syntax": yaml_summary,
        "schema": schema_summary,
        "extraction_rules": extraction_summary,
        "crawl_rules": crawl_rule_summary,
        "all_errors": all_errors,
        "all_warnings": all_warnings,
        "recommendations": recommendations,
    }


# List of all tools for easy import
CONFIG_VALIDATION_TOOLS = [
    validate_yaml_syntax,
    validate_schema,
    check_extraction_rules,
    check_crawl_rules,
    generate_validation_report,
]
