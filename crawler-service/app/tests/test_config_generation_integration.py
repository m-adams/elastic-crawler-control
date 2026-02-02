"""
Integration tests for config generation agent.

These tests verify the complete config generation flow from site analysis.
"""

import pytest
import yaml

from agents.config_generation import ConfigGenerationAgent
from agents.site_investigation import SiteInvestigationAgent


class TestConfigGenerationIntegration:
    """Integration tests for config generation."""
    
    @pytest.fixture
    def agent(self):
        """Create a config generation agent instance without LLM."""
        return ConfigGenerationAgent(
            use_agno=False,  # Skip LLM for basic testing
        )
    
    @pytest.fixture
    def sample_site_analysis(self):
        """Sample site analysis report for testing."""
        return {
            "domain": "https://example.com",
            "domain_name": "example.com",
            "status": "completed",
            "robots_txt": {
                "accessible": True,
                "sitemap_urls": [],
                "rules": [],
            },
            "sitemaps": {
                "total_urls_found": 0,
                "sample_urls": [],
            },
            "page_fetch_summary": {
                "total_attempted": 1,
                "successful": 1,
                "failed": 0,
                "bot_protection_detected": False,
            },
            "page_structure_analysis": {
                "common_classes": [],
                "common_navigation": [],
                "common_content_tags": [{"tag": "article", "count": 1}],
                "metadata_coverage": {
                    "has_author": "0%",
                    "has_date": "0%",
                    "has_description": "100%",
                },
            },
            "page_samples": [
                {
                    "url": "https://example.com/",
                    "headings": {"h1": ["Example Domain"]},
                    "metadata": {
                        "title": "Example Domain",
                        "description": "This domain is for examples.",
                    },
                    "content_areas": [],
                }
            ],
            "recommendations": {
                "crawl_rules": [],
                "extraction_rules": [],
            },
        }
    
    def test_generate_basic_config(self, agent, sample_site_analysis):
        """Test basic config generation from site analysis."""
        result = agent.generate(sample_site_analysis)
        
        assert result["status"] == "completed"
        assert result["domain"] == "https://example.com"
        assert "config" in result
        assert "yaml_content" in result
    
    def test_generated_config_is_valid_yaml(self, agent, sample_site_analysis):
        """Test that generated config is valid YAML."""
        result = agent.generate(sample_site_analysis)
        
        # Should parse without error
        config = yaml.safe_load(result["yaml_content"])
        
        assert "output_sink" in config
        assert "domains" in config
    
    def test_generated_config_has_required_fields(self, agent, sample_site_analysis):
        """Test that generated config has all required fields."""
        result = agent.generate(sample_site_analysis)
        config = result["config"]
        
        # Required top-level fields
        assert "output_sink" in config
        assert "domains" in config
        assert "max_crawl_depth" in config
        
        # Domain fields
        domain = config["domains"][0]
        assert "url" in domain
        assert "seed_urls" in domain
    
    def test_domain_url_format(self, agent, sample_site_analysis):
        """Test that domain URL is correctly formatted (no trailing slash)."""
        result = agent.generate(sample_site_analysis)
        config = result["config"]
        
        domain_url = config["domains"][0]["url"]
        assert not domain_url.endswith("/"), f"Domain URL has trailing slash: {domain_url}"
    
    def test_extraction_rules_have_join_as(self, agent, sample_site_analysis):
        """Test that all extraction rules have join_as field."""
        result = agent.generate(sample_site_analysis, content_type="blog")
        config = result["config"]
        
        domain = config["domains"][0]
        if "extraction_rulesets" in domain:
            for ruleset in domain["extraction_rulesets"]:
                for rule in ruleset.get("rules", []):
                    if rule.get("action") == "extract":
                        assert "join_as" in rule, f"Rule missing join_as: {rule}"
    
    def test_validation_passes(self, agent, sample_site_analysis):
        """Test that generated config passes validation."""
        result = agent.generate(sample_site_analysis)
        
        assert "validation" in result
        assert result["validation"]["valid"] is True
        assert len(result["validation"]["errors"]) == 0
    
    def test_content_type_detection(self, agent):
        """Test content type detection from analysis."""
        blog_analysis = {
            "domain": "https://blog.example.com",
            "page_structure_analysis": {
                "common_content_tags": [{"tag": "article", "count": 5}],
                "metadata_coverage": {
                    "has_author": "80%",
                    "has_date": "100%",
                    "has_description": "100%",
                },
            },
            "recommendations": {},
        }
        
        result = agent.generate(blog_analysis)
        
        assert result["content_type"] == "blog"
    
    def test_different_output_sinks(self, agent, sample_site_analysis):
        """Test generation for different output sinks."""
        # Console output
        result = agent.generate(sample_site_analysis, output_sink="console")
        assert result["config"]["output_sink"] == "console"
        
        # File output
        result = agent.generate(sample_site_analysis, output_sink="file")
        assert result["config"]["output_sink"] == "file"
        assert result["config"]["max_crawl_depth"] >= 1
        
        # Elasticsearch output
        result = agent.generate(
            sample_site_analysis,
            output_sink="elasticsearch",
            output_index="test-index"
        )
        assert result["config"]["output_sink"] == "elasticsearch"
        assert result["config"]["output_index"] == "test-index"
    
    def test_reasoning_provided(self, agent, sample_site_analysis):
        """Test that reasoning is provided for config decisions."""
        result = agent.generate(sample_site_analysis)
        
        assert "reasoning" in result
        assert len(result["reasoning"]) > 0
    
    def test_sample_document_provided(self, agent, sample_site_analysis):
        """Test that sample document preview is provided."""
        result = agent.generate(sample_site_analysis, content_type="blog")
        
        assert "sample_document" in result
        # Blog should have article-related fields
        assert "article_title" in result["sample_document"]
    
    def test_generate_from_domain(self, agent):
        """Test simplified generation from domain only."""
        result = agent.generate_from_domain("https://example.com")
        
        assert result["status"] == "completed"
        assert result["domain"] == "https://example.com"
        assert "yaml_content" in result
    
    def test_custom_fields(self, agent, sample_site_analysis):
        """Test adding custom extraction fields."""
        custom_fields = [
            {"field_name": "my_custom", "selector": ".custom-class", "join_as": "string"}
        ]
        
        result = agent.generate(
            sample_site_analysis,
            custom_fields=custom_fields
        )
        
        # Find the custom field in extraction rules
        domain = result["config"]["domains"][0]
        all_fields = [
            r["field_name"]
            for ruleset in domain.get("extraction_rulesets", [])
            for r in ruleset.get("rules", [])
        ]
        
        assert "my_custom" in all_fields


@pytest.mark.asyncio
class TestConfigGenerationFromRealSite:
    """
    Integration tests using real site investigation.
    
    These tests run the full pipeline: site investigation -> config generation.
    """
    
    @pytest.fixture
    def investigation_agent(self):
        """Create a site investigation agent."""
        return SiteInvestigationAgent(
            sample_page_count=3,  # Fewer pages for faster tests
            rate_limit_delay=0.5,
            llm_client=None,
        )
    
    @pytest.fixture
    def config_agent(self):
        """Create a config generation agent."""
        return ConfigGenerationAgent(
            use_agno=False,
        )
    
    async def test_full_pipeline_example_com(self, investigation_agent, config_agent):
        """
        Test full pipeline: investigate example.com -> generate config.
        
        This is the canonical integration test verifying end-to-end flow.
        """
        # Step 1: Investigate the site
        site_analysis = await investigation_agent.investigate("https://example.com")
        
        assert site_analysis["status"] in ["completed", "warning"]
        
        # Step 2: Generate config from analysis
        config_result = config_agent.generate(
            site_analysis,
            output_sink="file",
            output_dir="/config/results/example",
        )
        
        # Verify config generation succeeded
        assert config_result["status"] == "completed"
        assert config_result["validation"]["valid"] is True
        
        # Verify YAML is valid
        config = yaml.safe_load(config_result["yaml_content"])
        assert config["domains"][0]["url"] == "https://example.com"
        
        # Verify all extraction rules have join_as
        domain = config["domains"][0]
        if "extraction_rulesets" in domain:
            for ruleset in domain["extraction_rulesets"]:
                for rule in ruleset.get("rules", []):
                    if rule.get("action") == "extract":
                        assert "join_as" in rule
    
    async def test_pipeline_preserves_domain(self, investigation_agent, config_agent):
        """Test that domain is preserved through the pipeline."""
        site_analysis = await investigation_agent.investigate("example.com")
        config_result = config_agent.generate(site_analysis)
        
        # Domain should be normalized with https://
        assert config_result["config"]["domains"][0]["url"] == "https://example.com"


class TestConfigGenerationAgentClass:
    """Tests for ConfigGenerationAgent class methods."""
    
    def test_content_type_detection_ecommerce(self):
        """Test e-commerce content type detection."""
        agent = ConfigGenerationAgent(use_agno=False)
        
        analysis = {
            "domain": "https://shop.example.com",
            "page_structure_analysis": {
                "common_content_tags": [{"tag": "product", "count": 10}],
                "metadata_coverage": {},
            },
        }
        
        content_type = agent._detect_content_type(analysis)
        assert content_type == "ecommerce"
    
    def test_content_type_detection_docs(self):
        """Test documentation content type detection."""
        agent = ConfigGenerationAgent(use_agno=False)
        
        analysis = {
            "domain": "https://docs.example.com",
            "page_structure_analysis": {
                "common_content_tags": [],
                "metadata_coverage": {},
            },
        }
        
        content_type = agent._detect_content_type(analysis)
        assert content_type == "docs"
    
    def test_content_type_detection_general(self):
        """Test fallback to general content type."""
        agent = ConfigGenerationAgent(use_agno=False)
        
        analysis = {
            "domain": "https://example.com",
            "page_structure_analysis": {
                "common_content_tags": [],
                "metadata_coverage": {},
            },
        }
        
        content_type = agent._detect_content_type(analysis)
        assert content_type == "general"
    
    def test_error_handling_missing_domain(self):
        """Test error handling when domain is missing."""
        agent = ConfigGenerationAgent(use_agno=False)
        
        result = agent.generate({})  # Empty analysis
        
        assert result["status"] == "error"
        assert "domain" in result["error"].lower()


@pytest.mark.asyncio
@pytest.mark.slow
class TestConfigGenerationWithRealSites:
    """
    Tests with real websites (marked as slow).
    
    Run with: pytest -m slow
    Skip with: pytest -m "not slow"
    """
    
    @pytest.fixture
    def investigation_agent(self):
        """Create a site investigation agent."""
        return SiteInvestigationAgent(
            sample_page_count=5,
            rate_limit_delay=1.0,
            llm_client=None,
        )
    
    @pytest.fixture
    def config_agent(self):
        """Create a config generation agent."""
        return ConfigGenerationAgent(
            use_agno=False,
        )
    
    async def test_blog_site_config(self, investigation_agent, config_agent):
        """Test config generation for a blog site."""
        site_analysis = await investigation_agent.investigate("https://www.elastic.co/blog")
        
        if site_analysis["status"] in ["completed", "warning"]:
            config_result = config_agent.generate(
                site_analysis,
                output_sink="file",
                content_type="blog",
            )
            
            assert config_result["status"] == "completed"
            assert config_result["validation"]["valid"] is True
            
            # Should have blog-appropriate extraction rules
            domain = config_result["config"]["domains"][0]
            if "extraction_rulesets" in domain:
                field_names = [
                    r["field_name"]
                    for ruleset in domain["extraction_rulesets"]
                    for r in ruleset.get("rules", [])
                ]
                # Blog content types should extract article fields
                assert any("article" in f for f in field_names)
