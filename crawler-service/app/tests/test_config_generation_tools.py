"""
Unit tests for config generation tools.

Tests the Agno tools for generating Open Crawler configurations.
"""

import pytest
import yaml

from agents.config_generation_tools import (
    load_knowledge_patterns,
    generate_domain_config,
    generate_crawl_rules,
    generate_extraction_rules,
    generate_full_config,
    validate_config_structure,
    CONFIG_GENERATION_TOOLS,
)


class TestLoadKnowledgePatterns:
    """Tests for load_knowledge_patterns tool."""
    
    def test_load_base_config_patterns(self):
        """Test loading base config patterns."""
        result = load_knowledge_patterns("base-config")
        
        assert result["pattern_type"] == "base-config"
        assert result["error"] is None
        assert len(result["key_rules"]) > 0
        assert any("flat" in rule.lower() for rule in result["key_rules"])
    
    def test_load_extraction_basics_patterns(self):
        """Test loading extraction basics patterns."""
        result = load_knowledge_patterns("extraction-basics")
        
        assert result["pattern_type"] == "extraction-basics"
        assert result["error"] is None
        assert any("join_as" in rule.lower() for rule in result["key_rules"])
    
    def test_load_extraction_patterns(self):
        """Test loading extraction patterns."""
        result = load_knowledge_patterns("extraction-patterns")
        
        assert result["pattern_type"] == "extraction-patterns"
        assert result["error"] is None
        assert len(result["key_rules"]) > 0
    
    def test_load_crawl_rules_patterns(self):
        """Test loading crawl rules patterns."""
        result = load_knowledge_patterns("crawl-rules")
        
        assert result["pattern_type"] == "crawl-rules"
        assert result["error"] is None
        assert any("order" in rule.lower() for rule in result["key_rules"])
    
    def test_load_all_patterns(self):
        """Test loading summary of all patterns."""
        result = load_knowledge_patterns("all")
        
        assert result["pattern_type"] == "all"
        assert result["error"] is None
        assert len(result["key_rules"]) >= 5  # Should have multiple rules
    
    def test_load_unknown_pattern_type(self):
        """Test error handling for unknown pattern type."""
        result = load_knowledge_patterns("unknown-type")
        
        assert result["error"] is not None
        assert "unknown" in result["error"].lower()


class TestGenerateDomainConfig:
    """Tests for generate_domain_config tool."""
    
    def test_basic_domain_config(self):
        """Test basic domain config generation."""
        result = generate_domain_config("https://example.com")
        
        assert result["domain_config"]["url"] == "https://example.com"
        assert "seed_urls" in result["domain_config"]
        assert len(result["domain_config"]["seed_urls"]) > 0
        assert "yaml_snippet" in result
    
    def test_domain_trailing_slash_removed(self):
        """Test that trailing slash is removed from domain."""
        result = generate_domain_config("https://example.com/")
        
        assert result["domain_config"]["url"] == "https://example.com"
    
    def test_domain_path_removed(self):
        """Test that path is removed from domain URL."""
        result = generate_domain_config("https://example.com/blog/")
        
        assert result["domain_config"]["url"] == "https://example.com"
    
    def test_custom_seed_urls(self):
        """Test custom seed URLs are normalized."""
        result = generate_domain_config(
            "https://example.com",
            seed_urls=["/blog/", "/docs/"]
        )
        
        seed_urls = result["domain_config"]["seed_urls"]
        assert "https://example.com/blog/" in seed_urls
        assert "https://example.com/docs/" in seed_urls
    
    def test_yaml_snippet_valid(self):
        """Test that YAML snippet is valid YAML."""
        result = generate_domain_config("https://example.com")
        
        # Should parse without error
        parsed = yaml.safe_load(result["yaml_snippet"])
        assert "domains" in parsed


class TestGenerateCrawlRules:
    """Tests for generate_crawl_rules tool."""
    
    def test_basic_crawl_rules(self):
        """Test basic crawl rules generation."""
        site_analysis = {
            "recommendations": {
                "crawl_rules": []
            }
        }
        
        result = generate_crawl_rules(site_analysis)
        
        assert "crawl_rules" in result
        assert "reasoning" in result
    
    def test_crawl_rules_with_content_focus(self):
        """Test crawl rules with content focus."""
        site_analysis = {"recommendations": {}}
        
        result = generate_crawl_rules(site_analysis, content_focus="blog")
        
        # Should have allow rules for blog patterns
        allow_rules = [r for r in result["crawl_rules"] if r["policy"] == "allow"]
        assert len(allow_rules) > 0
        
        # Should end with deny all
        assert result["crawl_rules"][-1]["pattern"] == ".*"
    
    def test_crawl_rules_with_exclude_patterns(self):
        """Test crawl rules with explicit exclusions."""
        site_analysis = {"recommendations": {}}
        
        result = generate_crawl_rules(
            site_analysis,
            exclude_patterns=["search", "filter"]
        )
        
        # Should have deny rules for excluded patterns
        deny_patterns = [r["pattern"] for r in result["crawl_rules"] if r["policy"] == "deny"]
        assert "search" in deny_patterns
        assert "filter" in deny_patterns
    
    def test_crawl_rules_from_robots_txt(self):
        """Test crawl rules generated from robots.txt recommendations."""
        site_analysis = {
            "recommendations": {
                "crawl_rules": [
                    {
                        "type": "exclude_paths",
                        "patterns": ["/private/", "/admin/"],
                        "reason": "Disallowed by robots.txt"
                    }
                ]
            }
        }
        
        result = generate_crawl_rules(site_analysis)
        
        deny_patterns = [r["pattern"] for r in result["crawl_rules"] if r["policy"] == "deny"]
        assert "/private/" in deny_patterns
        assert "/admin/" in deny_patterns
    
    def test_crawl_rules_yaml_valid(self):
        """Test that YAML snippet is valid."""
        site_analysis = {"recommendations": {}}
        
        result = generate_crawl_rules(site_analysis, content_focus="docs")
        
        if result["yaml_snippet"]:
            parsed = yaml.safe_load(result["yaml_snippet"])
            assert "crawl_rules" in parsed


class TestGenerateExtractionRules:
    """Tests for generate_extraction_rules tool."""
    
    def test_blog_extraction_rules(self):
        """Test extraction rules for blog content."""
        site_analysis = {"page_structure_analysis": {}}
        
        result = generate_extraction_rules(site_analysis, content_type="blog")
        
        # Should have blog-specific fields
        field_names = [
            r["field_name"]
            for ruleset in result["extraction_rulesets"]
            for r in ruleset.get("rules", [])
        ]
        
        assert "article_title" in field_names
        assert "article_author" in field_names
        assert "publish_date" in field_names
    
    def test_ecommerce_extraction_rules(self):
        """Test extraction rules for e-commerce content."""
        site_analysis = {"page_structure_analysis": {}}
        
        result = generate_extraction_rules(site_analysis, content_type="ecommerce")
        
        field_names = [
            r["field_name"]
            for ruleset in result["extraction_rulesets"]
            for r in ruleset.get("rules", [])
        ]
        
        assert "product_name" in field_names
        assert "product_price" in field_names
    
    def test_docs_extraction_rules(self):
        """Test extraction rules for documentation content."""
        site_analysis = {"page_structure_analysis": {}}
        
        result = generate_extraction_rules(site_analysis, content_type="docs")
        
        field_names = [
            r["field_name"]
            for ruleset in result["extraction_rulesets"]
            for r in ruleset.get("rules", [])
        ]
        
        assert "doc_title" in field_names
        assert "doc_content" in field_names
    
    def test_all_rules_have_join_as(self):
        """Test that ALL extraction rules have join_as (CRITICAL)."""
        site_analysis = {"page_structure_analysis": {}}
        
        for content_type in ["blog", "ecommerce", "docs", "general"]:
            result = generate_extraction_rules(site_analysis, content_type=content_type)
            
            for ruleset in result["extraction_rulesets"]:
                for rule in ruleset.get("rules", []):
                    assert "join_as" in rule, (
                        f"Missing join_as in {content_type} rule: {rule.get('field_name')}"
                    )
                    assert rule["join_as"] in ["string", "array"]
    
    def test_no_reserved_field_names(self):
        """Test that no reserved field names are used."""
        reserved = ["id", "title", "body", "url", "links", "headings"]
        site_analysis = {"page_structure_analysis": {}}
        
        for content_type in ["blog", "ecommerce", "docs", "general"]:
            result = generate_extraction_rules(site_analysis, content_type=content_type)
            
            for ruleset in result["extraction_rulesets"]:
                for rule in ruleset.get("rules", []):
                    field_name = rule.get("field_name", "")
                    assert field_name not in reserved, (
                        f"Reserved field name used: {field_name}"
                    )
    
    def test_custom_fields_added(self):
        """Test that custom fields are added correctly."""
        site_analysis = {"page_structure_analysis": {}}
        custom_fields = [
            {"field_name": "my_custom_field", "selector": ".custom", "join_as": "string"}
        ]
        
        result = generate_extraction_rules(
            site_analysis,
            content_type="general",
            custom_fields=custom_fields
        )
        
        field_names = [
            r["field_name"]
            for ruleset in result["extraction_rulesets"]
            for r in ruleset.get("rules", [])
        ]
        
        assert "my_custom_field" in field_names
    
    def test_sample_document_provided(self):
        """Test that sample document is provided."""
        site_analysis = {"page_structure_analysis": {}}
        
        result = generate_extraction_rules(site_analysis, content_type="blog")
        
        assert "sample_document" in result
        assert len(result["sample_document"]) > 0
    
    def test_yaml_snippet_valid(self):
        """Test that YAML snippet is valid."""
        site_analysis = {"page_structure_analysis": {}}
        
        result = generate_extraction_rules(site_analysis, content_type="blog")
        
        parsed = yaml.safe_load(result["yaml_snippet"])
        assert "extraction_rulesets" in parsed


class TestGenerateFullConfig:
    """Tests for generate_full_config tool."""
    
    def test_console_output_config(self):
        """Test config with console output."""
        site_analysis = {
            "domain": "https://example.com",
            "recommendations": {},
            "page_structure_analysis": {},
        }
        
        result = generate_full_config(
            domain="https://example.com",
            site_analysis=site_analysis,
            output_sink="console",
        )
        
        assert result["config"]["output_sink"] == "console"
        assert "domains" in result["config"]
        assert result["config"]["domains"][0]["url"] == "https://example.com"
    
    def test_file_output_config(self):
        """Test config with file output."""
        site_analysis = {
            "domain": "https://example.com",
            "recommendations": {},
            "page_structure_analysis": {},
        }
        
        result = generate_full_config(
            domain="https://example.com",
            site_analysis=site_analysis,
            output_sink="file",
            output_dir="/config/results/test",
        )
        
        assert result["config"]["output_sink"] == "file"
        assert result["config"]["output_dir"] == "/config/results/test"
        assert result["config"]["max_crawl_depth"] >= 1  # Required for file output
    
    def test_elasticsearch_output_config(self):
        """Test config with Elasticsearch output."""
        site_analysis = {
            "domain": "https://example.com",
            "recommendations": {},
            "page_structure_analysis": {},
        }
        
        result = generate_full_config(
            domain="https://example.com",
            site_analysis=site_analysis,
            output_sink="elasticsearch",
            output_index="my-index",
        )
        
        assert result["config"]["output_sink"] == "elasticsearch"
        assert result["config"]["output_index"] == "my-index"
    
    def test_config_with_content_focus(self):
        """Test config with content focus generates crawl rules."""
        site_analysis = {
            "domain": "https://example.com",
            "recommendations": {},
            "page_structure_analysis": {},
        }
        
        result = generate_full_config(
            domain="https://example.com",
            site_analysis=site_analysis,
            output_sink="console",
            content_focus="blog",
        )
        
        domain_config = result["config"]["domains"][0]
        assert "crawl_rules" in domain_config
    
    def test_config_with_content_type(self):
        """Test config with content type generates extraction rules."""
        site_analysis = {
            "domain": "https://example.com",
            "recommendations": {},
            "page_structure_analysis": {},
        }
        
        result = generate_full_config(
            domain="https://example.com",
            site_analysis=site_analysis,
            output_sink="console",
            content_type="blog",
        )
        
        domain_config = result["config"]["domains"][0]
        assert "extraction_rulesets" in domain_config
    
    def test_yaml_content_parsable(self):
        """Test that generated YAML is parsable."""
        site_analysis = {
            "domain": "https://example.com",
            "recommendations": {},
            "page_structure_analysis": {},
        }
        
        result = generate_full_config(
            domain="https://example.com",
            site_analysis=site_analysis,
            output_sink="file",
            content_type="blog",
            content_focus="blog",
        )
        
        # Should parse without error
        parsed = yaml.safe_load(result["yaml_content"])
        assert "output_sink" in parsed
        assert "domains" in parsed
    
    def test_reasoning_provided(self):
        """Test that reasoning is provided for decisions."""
        site_analysis = {
            "domain": "https://example.com",
            "recommendations": {},
            "page_structure_analysis": {},
        }
        
        result = generate_full_config(
            domain="https://example.com",
            site_analysis=site_analysis,
            output_sink="file",
        )
        
        assert "reasoning" in result
        assert len(result["reasoning"]) > 0


class TestValidateConfigStructure:
    """Tests for validate_config_structure tool."""
    
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
        
        result = validate_config_structure(config)
        
        assert result["valid"] is True
        assert len(result["errors"]) == 0
    
    def test_missing_output_sink(self):
        """Test error when output_sink is missing."""
        config = {
            "domains": [{"url": "https://example.com"}]
        }
        
        result = validate_config_structure(config)
        
        assert result["valid"] is False
        assert any("output_sink" in e for e in result["errors"])
    
    def test_missing_domains(self):
        """Test error when domains is missing."""
        config = {
            "output_sink": "console"
        }
        
        result = validate_config_structure(config)
        
        assert result["valid"] is False
        assert any("domains" in e for e in result["errors"])
    
    def test_domain_trailing_slash_error(self):
        """Test error when domain URL has trailing slash."""
        config = {
            "output_sink": "console",
            "domains": [
                {
                    "url": "https://example.com/",  # Invalid - trailing slash
                    "seed_urls": ["https://example.com/"]
                }
            ]
        }
        
        result = validate_config_structure(config)
        
        assert result["valid"] is False
        assert any("trailing slash" in e for e in result["errors"])
    
    def test_missing_join_as_error(self):
        """Test error when extraction rule is missing join_as."""
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
                                    "source": "html",
                                    # Missing join_as!
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        result = validate_config_structure(config)
        
        assert result["valid"] is False
        assert any("join_as" in e for e in result["errors"])
    
    def test_reserved_field_name_warning(self):
        """Test warning when reserved field name is used."""
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
                                    "source": "html",
                                    "join_as": "string",
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        result = validate_config_structure(config)
        
        # Should be valid but with warning
        assert result["valid"] is True
        assert any("reserved" in w.lower() for w in result["warnings"])
    
    def test_file_output_depth_requirement(self):
        """Test error when file output with depth 0."""
        config = {
            "output_sink": "file",
            "max_crawl_depth": 0,  # Invalid for file output
            "domains": [
                {
                    "url": "https://example.com",
                    "seed_urls": ["https://example.com/"]
                }
            ]
        }
        
        result = validate_config_structure(config)
        
        assert result["valid"] is False
        assert any("max_crawl_depth" in e for e in result["errors"])


class TestToolsList:
    """Tests for the CONFIG_GENERATION_TOOLS list."""
    
    def test_all_tools_present(self):
        """Test that all tools are in the list."""
        assert load_knowledge_patterns in CONFIG_GENERATION_TOOLS
        assert generate_domain_config in CONFIG_GENERATION_TOOLS
        assert generate_crawl_rules in CONFIG_GENERATION_TOOLS
        assert generate_extraction_rules in CONFIG_GENERATION_TOOLS
        assert generate_full_config in CONFIG_GENERATION_TOOLS
        assert validate_config_structure in CONFIG_GENERATION_TOOLS
    
    def test_tools_count(self):
        """Test expected number of tools."""
        assert len(CONFIG_GENERATION_TOOLS) == 6
    
    def test_tools_are_callable(self):
        """Test that all tools are callable."""
        for tool in CONFIG_GENERATION_TOOLS:
            assert callable(tool)
    
    def test_tools_have_docstrings(self):
        """Test that all tools have docstrings."""
        for tool in CONFIG_GENERATION_TOOLS:
            assert tool.__doc__ is not None
            assert len(tool.__doc__) > 50  # Should have meaningful docstring
