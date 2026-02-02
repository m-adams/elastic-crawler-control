"""
Integration tests for site investigation agent.

These tests use a real website to verify the complete investigation flow.
"""

import pytest
from agents.site_investigation import SiteInvestigationAgent


@pytest.mark.asyncio
class TestSiteInvestigationIntegration:
    """Integration tests for site investigation."""
    
    @pytest.fixture
    def agent(self):
        """Create an agent instance without LLM for basic testing."""
        return SiteInvestigationAgent(
            sample_page_count=5,  # Fewer pages for faster tests
            rate_limit_delay=0.5,  # Faster for tests
            llm_client=None,  # Skip LLM analysis in tests
        )
    
    async def test_investigate_example_com(self, agent):
        """
        Test investigation of example.com (stable test site).
        
        This is a minimal test that verifies the basic flow works.
        """
        result = await agent.investigate("https://example.com")
        
        # Verify report structure
        assert result["domain"] == "https://example.com"
        assert result["domain_name"] == "example.com"
        assert result["status"] in ["completed", "warning"]
        
        # Verify robots.txt was checked
        assert "robots_txt" in result
        assert "accessible" in result["robots_txt"]
        
        # Verify sitemaps were checked
        assert "sitemaps" in result
        
        # Verify pages were fetched
        assert "page_fetch_summary" in result
        assert result["page_fetch_summary"]["total_attempted"] > 0
        
        # Verify structure analysis
        assert "page_structure_analysis" in result
        
        # Verify recommendations
        assert "recommendations" in result
        assert "crawl_rules" in result["recommendations"]
        assert "extraction_rules" in result["recommendations"]
    
    async def test_investigate_with_seed_urls(self, agent):
        """Test investigation with explicit seed URLs."""
        seed_urls = ["https://example.com/"]
        
        result = await agent.investigate(
            "https://example.com",
            seed_urls=seed_urls,
        )
        
        assert result["status"] in ["completed", "warning"]
        assert result["seed_urls"] == seed_urls
        assert result["page_fetch_summary"]["total_attempted"] > 0
    
    async def test_investigate_invalid_domain(self, agent):
        """Test investigation of invalid/unreachable domain."""
        result = await agent.investigate("https://this-domain-definitely-does-not-exist-12345.com")
        
        # Should handle gracefully
        assert "status" in result
        # May return error or warning depending on robots.txt fetch failure
        assert result["status"] in ["error", "warning", "completed"]
    
    async def test_investigate_domain_without_protocol(self, agent):
        """Test that domain normalization works."""
        result = await agent.investigate("example.com")
        
        # Should normalize to https://
        assert result["domain"] == "https://example.com"
        assert result["status"] in ["completed", "warning"]


@pytest.mark.asyncio
@pytest.mark.slow
class TestSiteInvestigationWithRealSites:
    """
    Tests with real websites (marked as slow).
    
    Run with: pytest -m slow
    Skip with: pytest -m "not slow"
    """
    
    @pytest.fixture
    def agent(self):
        """Create an agent instance."""
        return SiteInvestigationAgent(
            sample_page_count=10,
            rate_limit_delay=1.0,
            llm_client=None,
        )
    
    async def test_investigate_blog_site(self, agent):
        """Test investigation of a typical blog site."""
        # Using a stable, well-known blog
        result = await agent.investigate("https://www.elastic.co/blog")
        
        assert result["status"] in ["completed", "warning"]
        assert result["page_fetch_summary"]["successful"] > 0
        
        # Should identify blog-like content
        if result["page_samples"]:
            # Should find article-like structures
            sample = result["page_samples"][0]
            assert "headings" in sample
            assert "metadata" in sample
    
    async def test_investigate_with_sitemap(self, agent):
        """Test investigation of site with sitemap."""
        # Many sites have sitemaps
        result = await agent.investigate("https://www.elastic.co")
        
        if result["sitemaps"]["total_urls_found"] > 0:
            # If sitemap exists, should use it for sampling
            assert result["page_fetch_summary"]["total_attempted"] > 0
