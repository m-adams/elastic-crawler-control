"""
Unit tests for config validation tools.

Tests the Agno tools for validating Open Crawler configurations.
"""

import pytest
import yaml

from agents.config_validation_tools import (
    validate_yaml_syntax,
    validate_schema,
    check_extraction_rules,
    check_crawl_rules,
    generate_validation_report,
    CONFIG_VALIDATION_TOOLS,
    _apply_css_selector,
    _pattern_matches_url,
)


class TestValidateYamlSyntax:
    """Tests for validate_yaml_syntax tool."""
    
    def test_valid_yaml(self):
        """Test validation of valid YAML."""
        yaml_content = """
output_sink: console
domains:
  - url: https://example.com
    seed_urls:
      - https://example.com/
"""
        result = validate_yaml_syntax(yaml_content)
        
        assert result["valid"] is True
        assert result["error"] is None
        assert result["parsed_config"] is not None
        assert result["parsed_config"]["output_sink"] == "console"
    
    def test_invalid_yaml_syntax(self):
        """Test detection of YAML syntax errors."""
        yaml_content = """
output_sink: console
domains:
  - url: https://example.com
    seed_urls:
      - invalid: indentation
    here
"""
        result = validate_yaml_syntax(yaml_content)
        
        assert result["valid"] is False
        assert result["error"] is not None
        assert result["parsed_config"] is None
    
    def test_yaml_tabs_error(self):
        """Test detection of tab characters (common error)."""
        yaml_content = "output_sink: console\n\tdomains: []"
        result = validate_yaml_syntax(yaml_content)
        
        # Tabs cause YAML errors
        assert result["valid"] is False
        assert result["error"] is not None
    
    def test_empty_yaml(self):
        """Test handling of empty YAML."""
        result = validate_yaml_syntax("")
        
        # Empty string parses to None, which is not a dict
        assert result["valid"] is False
        assert "dictionary" in result["error"]
    
    def test_scalar_yaml(self):
        """Test rejection of scalar YAML values."""
        result = validate_yaml_syntax("just a string")
        
        assert result["valid"] is False
        assert "dictionary" in result["error"]
    
    def test_list_yaml(self):
        """Test rejection of list-only YAML."""
        result = validate_yaml_syntax("- item1\n- item2")
        
        assert result["valid"] is False
        assert "dictionary" in result["error"]
    
    def test_complex_valid_config(self):
        """Test validation of complex valid config."""
        yaml_content = """
output_sink: elasticsearch
output_index: my-content
max_crawl_depth: 3
domains:
  - url: https://example.com
    seed_urls:
      - https://example.com/blog/
    crawl_rules:
      - policy: allow
        type: begins
        pattern: /blog/
      - policy: deny
        type: regex
        pattern: ".*"
    extraction_rulesets:
      - rules:
          - action: extract
            field_name: article_title
            selector: h1
            source: html
            join_as: string
"""
        result = validate_yaml_syntax(yaml_content)
        
        assert result["valid"] is True
        assert result["parsed_config"]["output_sink"] == "elasticsearch"
        assert len(result["parsed_config"]["domains"]) == 1


class TestValidateSchema:
    """Tests for validate_schema tool."""
    
    def test_valid_minimal_config(self):
        """Test validation of minimal valid config."""
        config = {
            "output_sink": "console",
            "domains": [
                {
                    "url": "https://example.com",
                    "seed_urls": ["https://example.com/"]
                }
            ]
        }
        
        result = validate_schema(config)
        
        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert result["field_coverage"]["output_sink"] is True
        assert result["field_coverage"]["domains"] is True
    
    def test_missing_output_sink(self):
        """Test error when output_sink is missing."""
        config = {
            "domains": [{"url": "https://example.com"}]
        }
        
        result = validate_schema(config)
        
        assert result["valid"] is False
        assert any("output_sink" in e for e in result["errors"])
    
    def test_invalid_output_sink(self):
        """Test error when output_sink is invalid."""
        config = {
            "output_sink": "invalid",
            "domains": [{"url": "https://example.com"}]
        }
        
        result = validate_schema(config)
        
        assert result["valid"] is False
        assert any("output_sink" in e and "invalid" in e for e in result["errors"])
    
    def test_missing_domains(self):
        """Test error when domains is missing."""
        config = {
            "output_sink": "console"
        }
        
        result = validate_schema(config)
        
        assert result["valid"] is False
        assert any("domains" in e for e in result["errors"])
    
    def test_empty_domains(self):
        """Test error when domains list is empty."""
        config = {
            "output_sink": "console",
            "domains": []
        }
        
        result = validate_schema(config)
        
        assert result["valid"] is False
        assert any("empty" in e for e in result["errors"])
    
    def test_domain_trailing_slash(self):
        """Test error when domain URL has trailing slash."""
        config = {
            "output_sink": "console",
            "domains": [
                {
                    "url": "https://example.com/",  # Invalid
                    "seed_urls": ["https://example.com/"]
                }
            ]
        }
        
        result = validate_schema(config)
        
        assert result["valid"] is False
        assert any("trailing slash" in e for e in result["errors"])
    
    def test_missing_url_in_domain(self):
        """Test error when domain is missing url field."""
        config = {
            "output_sink": "console",
            "domains": [
                {
                    "seed_urls": ["https://example.com/"]
                }
            ]
        }
        
        result = validate_schema(config)
        
        assert result["valid"] is False
        assert any("Missing" in e and "url" in e for e in result["errors"])
    
    def test_warning_no_seed_urls(self):
        """Test warning when no seed_urls specified."""
        config = {
            "output_sink": "console",
            "domains": [
                {
                    "url": "https://example.com"
                }
            ]
        }
        
        result = validate_schema(config)
        
        assert result["valid"] is True  # Warning, not error
        assert any("seed_urls" in w for w in result["warnings"])
    
    def test_crawl_rule_validation(self):
        """Test validation of crawl rules."""
        config = {
            "output_sink": "console",
            "domains": [
                {
                    "url": "https://example.com",
                    "seed_urls": ["https://example.com/"],
                    "crawl_rules": [
                        {"policy": "allow", "type": "begins", "pattern": "/blog/"},
                        {"policy": "deny", "type": "invalid_type", "pattern": ".*"},
                    ]
                }
            ]
        }
        
        result = validate_schema(config)
        
        assert result["valid"] is False
        assert any("invalid_type" in e.lower() for e in result["errors"])
    
    def test_missing_join_as_error(self):
        """Test error when extraction rule missing join_as."""
        config = {
            "output_sink": "console",
            "domains": [
                {
                    "url": "https://example.com",
                    "seed_urls": ["https://example.com/"],
                    "extraction_rulesets": [
                        {
                            "rules": [
                                {
                                    "action": "extract",
                                    "field_name": "test",
                                    "selector": ".test",
                                    # Missing join_as!
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        result = validate_schema(config)
        
        assert result["valid"] is False
        assert any("join_as" in e for e in result["errors"])
    
    def test_reserved_field_name_warning(self):
        """Test warning for reserved field names."""
        config = {
            "output_sink": "console",
            "domains": [
                {
                    "url": "https://example.com",
                    "seed_urls": ["https://example.com/"],
                    "extraction_rulesets": [
                        {
                            "rules": [
                                {
                                    "action": "extract",
                                    "field_name": "title",  # Reserved!
                                    "selector": "h1",
                                    "join_as": "string",
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        result = validate_schema(config)
        
        assert result["valid"] is True  # Warning, not error
        assert any("reserved" in w.lower() for w in result["warnings"])
    
    def test_file_output_depth_requirement(self):
        """Test error when file output with depth < 1."""
        config = {
            "output_sink": "file",
            "max_crawl_depth": 0,
            "domains": [
                {
                    "url": "https://example.com",
                    "seed_urls": ["https://example.com/"]
                }
            ]
        }
        
        result = validate_schema(config)
        
        assert result["valid"] is False
        assert any("max_crawl_depth" in e for e in result["errors"])
    
    def test_elasticsearch_warnings(self):
        """Test warnings for elasticsearch output without config."""
        config = {
            "output_sink": "elasticsearch",
            "domains": [
                {
                    "url": "https://example.com",
                    "seed_urls": ["https://example.com/"]
                }
            ]
        }
        
        result = validate_schema(config)
        
        assert result["valid"] is True
        assert any("output_index" in w for w in result["warnings"])


class TestApplyCssSelector:
    """Tests for the _apply_css_selector helper function."""
    
    def test_simple_selector(self):
        """Test simple CSS selector."""
        html = "<html><body><h1>Hello World</h1></body></html>"
        result = _apply_css_selector(html, "h1")
        
        assert result == ["Hello World"]
    
    def test_class_selector(self):
        """Test class-based selector."""
        html = '<html><body><div class="content">Main content</div></body></html>'
        result = _apply_css_selector(html, ".content")
        
        assert result == ["Main content"]
    
    def test_multiple_matches(self):
        """Test selector matching multiple elements."""
        html = "<html><body><p>First</p><p>Second</p><p>Third</p></body></html>"
        result = _apply_css_selector(html, "p")
        
        assert result == ["First", "Second", "Third"]
    
    def test_no_match(self):
        """Test selector with no matches."""
        html = "<html><body><div>No paragraphs here</div></body></html>"
        result = _apply_css_selector(html, "p")
        
        assert result == []
    
    def test_complex_selector(self):
        """Test complex CSS selector."""
        html = '<html><body><article><h1 class="title">Article Title</h1></article></body></html>'
        result = _apply_css_selector(html, "article h1.title")
        
        assert result == ["Article Title"]
    
    def test_empty_elements_filtered(self):
        """Test that empty elements are filtered out."""
        html = "<html><body><p>Content</p><p>   </p><p></p></body></html>"
        result = _apply_css_selector(html, "p")
        
        assert result == ["Content"]


class TestPatternMatchesUrl:
    """Tests for the _pattern_matches_url helper function."""
    
    def test_begins_match(self):
        """Test 'begins' pattern type."""
        assert _pattern_matches_url("/blog/", "begins", "https://example.com/blog/post") is True
        assert _pattern_matches_url("/blog/", "begins", "https://example.com/products/") is False
    
    def test_ends_match(self):
        """Test 'ends' pattern type."""
        assert _pattern_matches_url(".html", "ends", "https://example.com/page.html") is True
        assert _pattern_matches_url(".html", "ends", "https://example.com/page.php") is False
    
    def test_contains_match(self):
        """Test 'contains' pattern type."""
        assert _pattern_matches_url("search", "contains", "https://example.com/search?q=test") is True
        assert _pattern_matches_url("?", "contains", "https://example.com/page?param=value") is True
        assert _pattern_matches_url("admin", "contains", "https://example.com/page") is False
    
    def test_regex_match(self):
        """Test 'regex' pattern type."""
        assert _pattern_matches_url(r"\.html$", "regex", "https://example.com/page.html") is True
        assert _pattern_matches_url(r"/blog/\d+", "regex", "https://example.com/blog/123") is True
        assert _pattern_matches_url(r"/blog/\d+", "regex", "https://example.com/blog/post") is False
    
    def test_equals_match(self):
        """Test 'equals' pattern type."""
        assert _pattern_matches_url("/about", "equals", "https://example.com/about") is True
        assert _pattern_matches_url("/about", "equals", "https://example.com/about/team") is False
    
    def test_invalid_regex_returns_false(self):
        """Test that invalid regex patterns return False."""
        result = _pattern_matches_url("[invalid", "regex", "https://example.com/page")
        assert result is False


class TestCheckExtractionRules:
    """Tests for check_extraction_rules tool."""
    
    def test_extraction_with_matching_selectors(self):
        """Test extraction rules that match content."""
        config = {
            "domains": [
                {
                    "url": "https://example.com",
                    "extraction_rulesets": [
                        {
                            "rules": [
                                {
                                    "action": "extract",
                                    "field_name": "page_title",
                                    "selector": "h1",
                                    "join_as": "string",
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        sample_pages = [
            {
                "url": "https://example.com/page1",
                "html_content": "<html><body><h1>Page Title</h1></body></html>",
            }
        ]
        
        result = check_extraction_rules(config, sample_pages)
        
        assert result["total_pages"] == 1
        assert result["total_rules"] == 1
        assert "page_title" in result["results_by_field"]
        assert result["results_by_field"]["page_title"]["pages_matched"] == 1
        assert len(result["issues"]) == 0
    
    def test_extraction_with_non_matching_selectors(self):
        """Test extraction rules that don't match content."""
        config = {
            "domains": [
                {
                    "url": "https://example.com",
                    "extraction_rulesets": [
                        {
                            "rules": [
                                {
                                    "action": "extract",
                                    "field_name": "nonexistent",
                                    "selector": ".does-not-exist",
                                    "join_as": "string",
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        sample_pages = [
            {
                "url": "https://example.com/page1",
                "html_content": "<html><body><h1>Title</h1></body></html>",
            }
        ]
        
        result = check_extraction_rules(config, sample_pages)
        
        assert result["results_by_field"]["nonexistent"]["pages_matched"] == 0
        assert any("matched 0 pages" in issue for issue in result["issues"])
    
    def test_extraction_no_rules(self):
        """Test handling when config has no extraction rules."""
        config = {
            "domains": [
                {
                    "url": "https://example.com",
                }
            ]
        }
        
        sample_pages = [{"url": "https://example.com", "html_content": "<html></html>"}]
        
        result = check_extraction_rules(config, sample_pages)
        
        assert result["total_rules"] == 0
        assert "No extraction rules" in result["issues"][0]
    
    def test_extraction_no_pages(self):
        """Test handling when no sample pages provided."""
        config = {
            "domains": [
                {
                    "url": "https://example.com",
                    "extraction_rulesets": [
                        {"rules": [{"action": "extract", "field_name": "test", "selector": "h1", "join_as": "string"}]}
                    ]
                }
            ]
        }
        
        result = check_extraction_rules(config, [])
        
        assert result["total_pages"] == 0
        assert "No sample pages" in result["issues"][0]
    
    def test_extraction_multiple_pages_with_low_match_rate(self):
        """Test extraction across multiple pages with low match rate."""
        config = {
            "domains": [
                {
                    "url": "https://example.com",
                    "extraction_rulesets": [
                        {
                            "rules": [
                                {"action": "extract", "field_name": "heading", "selector": "h1", "join_as": "string"}
                            ]
                        }
                    ]
                }
            ]
        }
        
        # Only 1 out of 5 pages has a heading (20% match rate < 50% threshold)
        sample_pages = [
            {"url": "https://example.com/p1", "html_content": "<html><body><h1>One</h1></body></html>"},
            {"url": "https://example.com/p2", "html_content": "<html><body><p>No heading</p></body></html>"},
            {"url": "https://example.com/p3", "html_content": "<html><body><p>No heading</p></body></html>"},
            {"url": "https://example.com/p4", "html_content": "<html><body><p>No heading</p></body></html>"},
            {"url": "https://example.com/p5", "html_content": "<html><body><p>No heading</p></body></html>"},
        ]
        
        result = check_extraction_rules(config, sample_pages)
        
        assert result["total_pages"] == 5
        assert result["results_by_field"]["heading"]["pages_matched"] == 1
        # Low match rate warning (1/5 = 20% < 50%)
        assert any("low match rate" in issue.lower() for issue in result["issues"])
    
    def test_extraction_multiple_pages_good_match_rate(self):
        """Test extraction across multiple pages with good match rate."""
        config = {
            "domains": [
                {
                    "url": "https://example.com",
                    "extraction_rulesets": [
                        {
                            "rules": [
                                {"action": "extract", "field_name": "heading", "selector": "h1", "join_as": "string"}
                            ]
                        }
                    ]
                }
            ]
        }
        
        # 2 out of 3 pages have headings (66.7% match rate > 50% threshold)
        sample_pages = [
            {"url": "https://example.com/p1", "html_content": "<html><body><h1>One</h1></body></html>"},
            {"url": "https://example.com/p2", "html_content": "<html><body><h1>Two</h1></body></html>"},
            {"url": "https://example.com/p3", "html_content": "<html><body><p>No heading</p></body></html>"},
        ]
        
        result = check_extraction_rules(config, sample_pages)
        
        assert result["total_pages"] == 3
        assert result["results_by_field"]["heading"]["pages_matched"] == 2
        # No low match rate warning since 66.7% > 50%
        assert not any("low match rate" in issue.lower() for issue in result["issues"])


class TestCheckCrawlRules:
    """Tests for check_crawl_rules tool."""
    
    def test_crawl_rules_allow(self):
        """Test crawl rules that allow URLs."""
        config = {
            "domains": [
                {
                    "url": "https://example.com",
                    "seed_urls": ["https://example.com/blog/"],
                    "crawl_rules": [
                        {"policy": "allow", "type": "begins", "pattern": "/blog/"},
                        {"policy": "deny", "type": "regex", "pattern": ".*"},
                    ]
                }
            ]
        }
        
        sample_urls = [
            "https://example.com/blog/post-1",
            "https://example.com/blog/post-2",
            "https://example.com/products/item",
        ]
        
        result = check_crawl_rules(config, sample_urls)
        
        assert len(result["allowed_urls"]) == 2
        assert len(result["denied_urls"]) == 1
        assert "https://example.com/blog/post-1" in result["allowed_urls"]
        assert "https://example.com/products/item" in result["denied_urls"]
    
    def test_crawl_rules_deny(self):
        """Test crawl rules that deny URLs."""
        config = {
            "domains": [
                {
                    "url": "https://example.com",
                    "crawl_rules": [
                        {"policy": "deny", "type": "begins", "pattern": "/admin/"},
                        {"policy": "deny", "type": "contains", "pattern": "?"},
                    ]
                }
            ]
        }
        
        sample_urls = [
            "https://example.com/admin/dashboard",
            "https://example.com/search?q=test",
            "https://example.com/blog/",
        ]
        
        result = check_crawl_rules(config, sample_urls)
        
        assert "https://example.com/admin/dashboard" in result["denied_urls"]
        assert "https://example.com/search?q=test" in result["denied_urls"]
        assert "https://example.com/blog/" in result["allowed_urls"]
    
    def test_no_crawl_rules(self):
        """Test handling when no crawl rules defined."""
        config = {
            "domains": [
                {
                    "url": "https://example.com",
                }
            ]
        }
        
        sample_urls = ["/page1", "/page2"]
        
        result = check_crawl_rules(config, sample_urls)
        
        assert result["total_rules"] == 0
        assert len(result["allowed_urls"]) == 2
        assert "No crawl rules" in result["issues"][0]
    
    def test_seed_url_denied_warning(self):
        """Test warning when seed URL would be denied."""
        config = {
            "domains": [
                {
                    "url": "https://example.com",
                    "seed_urls": ["https://example.com/blog/"],
                    "crawl_rules": [
                        {"policy": "deny", "type": "begins", "pattern": "/blog/"},
                    ]
                }
            ]
        }
        
        sample_urls = ["https://example.com/page"]
        
        result = check_crawl_rules(config, sample_urls)
        
        assert any("Seed URL" in issue and "DENIED" in issue for issue in result["issues"])
    
    def test_rule_order_warning(self):
        """Test warning when allow rule after deny-all."""
        config = {
            "domains": [
                {
                    "url": "https://example.com",
                    "crawl_rules": [
                        {"policy": "deny", "type": "regex", "pattern": ".*"},  # Deny all first
                        {"policy": "allow", "type": "begins", "pattern": "/blog/"},  # Unreachable!
                    ]
                }
            ]
        }
        
        sample_urls = ["https://example.com/blog/post"]
        
        result = check_crawl_rules(config, sample_urls)
        
        assert any("never be reached" in issue.lower() for issue in result["issues"])


class TestGenerateValidationReport:
    """Tests for generate_validation_report tool."""
    
    def test_report_all_pass(self):
        """Test report generation when all validations pass."""
        yaml_result = {"valid": True}
        schema_result = {"valid": True, "errors": [], "warnings": [], "field_coverage": {}}
        
        report = generate_validation_report(yaml_result, schema_result)
        
        assert report["overall_status"] == "pass"
        assert len(report["all_errors"]) == 0
        assert len(report["all_warnings"]) == 0
    
    def test_report_yaml_error(self):
        """Test report generation with YAML error."""
        yaml_result = {"valid": False, "error": "Invalid syntax at line 5", "line_number": 5}
        schema_result = {"valid": False, "errors": [], "warnings": []}
        
        report = generate_validation_report(yaml_result, schema_result)
        
        assert report["overall_status"] == "fail"
        assert any("YAML" in e for e in report["all_errors"])
        assert any("line 5" in r for r in report["recommendations"])
    
    def test_report_schema_errors(self):
        """Test report generation with schema errors."""
        yaml_result = {"valid": True}
        schema_result = {
            "valid": False,
            "errors": ["Missing output_sink", "Missing join_as"],
            "warnings": [],
            "field_coverage": {},
        }
        
        report = generate_validation_report(yaml_result, schema_result)
        
        assert report["overall_status"] == "fail"
        assert len(report["all_errors"]) == 2
        assert any("output_sink" in r for r in report["recommendations"])
        assert any("join_as" in r for r in report["recommendations"])
    
    def test_report_warnings_only(self):
        """Test report generation with only warnings."""
        yaml_result = {"valid": True}
        schema_result = {
            "valid": True,
            "errors": [],
            "warnings": ["Reserved field name used"],
            "field_coverage": {},
        }
        
        report = generate_validation_report(yaml_result, schema_result)
        
        assert report["overall_status"] == "warning"
        assert len(report["all_errors"]) == 0
        assert len(report["all_warnings"]) == 1
    
    def test_report_with_extraction_results(self):
        """Test report includes extraction test results."""
        yaml_result = {"valid": True}
        schema_result = {"valid": True, "errors": [], "warnings": [], "field_coverage": {}}
        extraction_result = {
            "total_pages": 5,
            "total_rules": 3,
            "summary": {"extraction_success_rate": "80%"},
            "issues": ["Field 'author' has low match rate"],
        }
        
        report = generate_validation_report(yaml_result, schema_result, extraction_result)
        
        assert report["extraction_rules"]["tested"] is True
        assert report["extraction_rules"]["total_pages"] == 5
        assert any("author" in w.lower() for w in report["all_warnings"])
    
    def test_report_with_crawl_rule_results(self):
        """Test report includes crawl rule test results."""
        yaml_result = {"valid": True}
        schema_result = {"valid": True, "errors": [], "warnings": [], "field_coverage": {}}
        crawl_result = {
            "total_urls": 10,
            "total_rules": 5,
            "allowed_urls": ["url1", "url2"],
            "denied_urls": ["url3"],
            "issues": [],
        }
        
        report = generate_validation_report(yaml_result, schema_result, None, crawl_result)
        
        assert report["crawl_rules"]["tested"] is True
        assert report["crawl_rules"]["allowed_count"] == 2
        assert report["crawl_rules"]["denied_count"] == 1
    
    def test_report_seed_url_denied_is_error(self):
        """Test that denied seed URLs are reported as errors."""
        yaml_result = {"valid": True}
        schema_result = {"valid": True, "errors": [], "warnings": [], "field_coverage": {}}
        crawl_result = {
            "total_urls": 5,
            "total_rules": 2,
            "allowed_urls": [],
            "denied_urls": ["url1"],
            "issues": ["Seed URL '/blog/' would be DENIED by rule"],
        }
        
        report = generate_validation_report(yaml_result, schema_result, None, crawl_result)
        
        assert report["overall_status"] == "fail"
        assert any("Seed URL" in e for e in report["all_errors"])


class TestToolsList:
    """Tests for the CONFIG_VALIDATION_TOOLS list."""
    
    def test_all_tools_present(self):
        """Test that all tools are in the list."""
        assert validate_yaml_syntax in CONFIG_VALIDATION_TOOLS
        assert validate_schema in CONFIG_VALIDATION_TOOLS
        assert check_extraction_rules in CONFIG_VALIDATION_TOOLS
        assert check_crawl_rules in CONFIG_VALIDATION_TOOLS
        assert generate_validation_report in CONFIG_VALIDATION_TOOLS
    
    def test_tools_count(self):
        """Test expected number of tools."""
        assert len(CONFIG_VALIDATION_TOOLS) == 5
    
    def test_tools_are_callable(self):
        """Test that all tools are callable."""
        for tool in CONFIG_VALIDATION_TOOLS:
            assert callable(tool)
    
    def test_tools_have_docstrings(self):
        """Test that all tools have docstrings."""
        for tool in CONFIG_VALIDATION_TOOLS:
            assert tool.__doc__ is not None
            assert len(tool.__doc__) > 50  # Should have meaningful docstring


class TestConfigValidationAgentIntegration:
    """Integration tests for ConfigValidationAgent."""
    
    def test_validate_sync_valid_config(self):
        """Test synchronous validation of valid config."""
        from agents.config_validation import ConfigValidationAgent
        
        agent = ConfigValidationAgent(use_agno=False)
        
        config = {
            "output_sink": "console",
            "domains": [
                {
                    "url": "https://example.com",
                    "seed_urls": ["https://example.com/"],
                    "extraction_rulesets": [
                        {
                            "rules": [
                                {
                                    "action": "extract",
                                    "field_name": "page_title",
                                    "selector": "h1",
                                    "join_as": "string",
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        result = agent.validate_sync(config)
        
        assert result["overall_status"] in ["pass", "warning"]
        assert result["schema_validation"]["valid"] is True
    
    def test_validate_sync_invalid_config(self):
        """Test synchronous validation of invalid config."""
        from agents.config_validation import ConfigValidationAgent
        
        agent = ConfigValidationAgent(use_agno=False)
        
        config = {
            # Missing output_sink
            "domains": [
                {
                    "url": "https://example.com/",  # Has trailing slash (invalid)
                }
            ]
        }
        
        result = agent.validate_sync(config)
        
        assert result["overall_status"] == "fail"
        assert result["schema_validation"]["valid"] is False
    
    def test_validate_sync_with_yaml_string(self):
        """Test validation with YAML string input."""
        from agents.config_validation import ConfigValidationAgent
        
        agent = ConfigValidationAgent(use_agno=False)
        
        yaml_content = """
output_sink: file
output_dir: /config/results
max_crawl_depth: 2
domains:
  - url: https://example.com
    seed_urls:
      - https://example.com/
"""
        
        result = agent.validate_sync(yaml_content)
        
        assert result["yaml_validation"]["valid"] is True
        assert result["overall_status"] in ["pass", "warning"]
    
    def test_validate_yaml_only(self):
        """Test YAML-only validation."""
        from agents.config_validation import ConfigValidationAgent
        
        agent = ConfigValidationAgent(use_agno=False)
        
        valid_yaml = "output_sink: console\ndomains: []"
        result = agent.validate_yaml_only(valid_yaml)
        assert result["valid"] is True
        
        invalid_yaml = "invalid: yaml: here:"
        result = agent.validate_yaml_only(invalid_yaml)
        assert result["valid"] is False
    
    def test_validate_schema_only(self):
        """Test schema-only validation."""
        from agents.config_validation import ConfigValidationAgent
        
        agent = ConfigValidationAgent(use_agno=False)
        
        config = {
            "output_sink": "console",
            "domains": [{"url": "https://example.com", "seed_urls": ["https://example.com/"]}]
        }
        
        result = agent.validate_schema_only(config)
        assert result["valid"] is True
    
    def test_validate_sync_with_sample_pages(self):
        """Test validation with sample pages for extraction testing."""
        from agents.config_validation import ConfigValidationAgent
        
        agent = ConfigValidationAgent(use_agno=False)
        
        config = {
            "output_sink": "console",
            "domains": [
                {
                    "url": "https://example.com",
                    "seed_urls": ["https://example.com/"],
                    "extraction_rulesets": [
                        {
                            "rules": [
                                {
                                    "action": "extract",
                                    "field_name": "article_title",
                                    "selector": "h1.title",
                                    "join_as": "string",
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        sample_pages = [
            {
                "url": "https://example.com/post-1",
                "html_content": '<html><body><h1 class="title">Post One</h1></body></html>',
            },
            {
                "url": "https://example.com/post-2",
                "html_content": '<html><body><h1 class="title">Post Two</h1></body></html>',
            },
        ]
        
        result = agent.validate_sync(config, sample_pages=sample_pages)
        
        assert "extraction_test" in result
        assert result["extraction_test"]["total_pages"] == 2
        assert result["extraction_test"]["results_by_field"]["article_title"]["pages_matched"] == 2
