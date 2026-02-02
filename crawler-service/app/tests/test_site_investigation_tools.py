"""
Unit tests for site investigation Agno tools.

These tests verify that:
1. Tool functions have correct signatures for Agno
2. Tools return JSON-serializable results
3. Tools handle errors gracefully
4. The SITE_INVESTIGATION_TOOLS list contains all tools
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from agents.site_investigation_tools import (
    fetch_robots_txt,
    fetch_sitemap_urls,
    fetch_pages,
    analyze_page_structure,
    analyze_page_patterns,
    select_sample_urls,
    generate_recommendations,
    SITE_INVESTIGATION_TOOLS,
    reset_tool_instances,
)


class TestToolFunctions:
    """Test that tool functions have correct signatures."""
    
    def setup_method(self):
        """Reset tool instances before each test."""
        reset_tool_instances()
    
    def test_all_tools_in_list(self):
        """Verify SITE_INVESTIGATION_TOOLS contains all expected tools."""
        expected_tools = [
            fetch_robots_txt,
            fetch_sitemap_urls,
            fetch_pages,
            analyze_page_structure,
            analyze_page_patterns,
            select_sample_urls,
            generate_recommendations,
        ]
        
        assert len(SITE_INVESTIGATION_TOOLS) == len(expected_tools)
        for tool in expected_tools:
            assert tool in SITE_INVESTIGATION_TOOLS
    
    def test_tools_have_docstrings(self):
        """All tools should have descriptive docstrings for LLM understanding."""
        for tool in SITE_INVESTIGATION_TOOLS:
            assert tool.__doc__ is not None
            assert len(tool.__doc__) > 50  # Meaningful docstring
    
    def test_tools_are_callable(self):
        """All tools should be callable."""
        for tool in SITE_INVESTIGATION_TOOLS:
            assert callable(tool)


class TestFetchRobotsTxt:
    """Tests for fetch_robots_txt tool."""
    
    def setup_method(self):
        """Reset tool instances before each test."""
        reset_tool_instances()
    
    def test_normalizes_domain_without_protocol(self):
        """Should add https:// to domain without protocol."""
        with patch('agents.site_investigation_tools._get_robots_parser') as mock:
            mock_parser = MagicMock()
            mock.return_value = mock_parser
            
            # Mock async method
            from utils.robots_parser import RobotsData, RobotsRule
            mock_data = RobotsData(
                raw_content="",
                rules=[],
                sitemaps=[],
                accessible=True,
            )
            mock_parser.fetch_and_parse = AsyncMock(return_value=mock_data)
            
            result = fetch_robots_txt("example.com")
            
            # Verify domain was normalized
            mock_parser.fetch_and_parse.assert_called_once()
            call_args = mock_parser.fetch_and_parse.call_args[0][0]
            assert call_args.startswith("https://")
    
    def test_returns_dict_structure(self):
        """Should return proper dictionary structure."""
        with patch('agents.site_investigation_tools._get_robots_parser') as mock:
            mock_parser = MagicMock()
            mock.return_value = mock_parser
            
            from utils.robots_parser import RobotsData, RobotsRule
            mock_data = RobotsData(
                raw_content="User-agent: *\nDisallow: /admin/",
                rules=[RobotsRule(user_agent="*", allow=[], disallow=["/admin/"])],
                sitemaps=["https://example.com/sitemap.xml"],
                accessible=True,
            )
            mock_parser.fetch_and_parse = AsyncMock(return_value=mock_data)
            
            result = fetch_robots_txt("https://example.com")
            
            assert "accessible" in result
            assert "error" in result
            assert "sitemap_urls" in result
            assert "rules" in result
            assert result["accessible"] is True
            assert result["sitemap_urls"] == ["https://example.com/sitemap.xml"]
    
    def test_handles_error_gracefully(self):
        """Should handle fetch errors gracefully."""
        with patch('agents.site_investigation_tools._get_robots_parser') as mock:
            mock_parser = MagicMock()
            mock.return_value = mock_parser
            mock_parser.fetch_and_parse = AsyncMock(side_effect=Exception("Connection error"))
            
            result = fetch_robots_txt("https://example.com")
            
            assert result["accessible"] is False
            assert "error" in result
            assert "Connection error" in result["error"]


class TestFetchSitemapUrls:
    """Tests for fetch_sitemap_urls tool."""
    
    def setup_method(self):
        """Reset tool instances before each test."""
        reset_tool_instances()
    
    def test_empty_sitemap_list(self):
        """Should handle empty sitemap list."""
        result = fetch_sitemap_urls([])
        
        assert result["total_urls_found"] == 0
        assert result["sample_urls"] == []
        assert result["error"] is None
    
    def test_returns_dict_structure(self):
        """Should return proper dictionary structure."""
        with patch('agents.site_investigation_tools._get_sitemap_parser') as mock:
            mock_parser = MagicMock()
            mock.return_value = mock_parser
            
            from utils.sitemap_parser import SitemapURL
            mock_urls = [
                SitemapURL(loc="https://example.com/page1"),
                SitemapURL(loc="https://example.com/page2"),
            ]
            mock_parser.fetch_all_urls = AsyncMock(return_value=mock_urls)
            
            result = fetch_sitemap_urls(["https://example.com/sitemap.xml"])
            
            assert "total_urls_found" in result
            assert "sample_urls" in result
            assert "error" in result
            assert result["total_urls_found"] == 2


class TestFetchPages:
    """Tests for fetch_pages tool."""
    
    def setup_method(self):
        """Reset tool instances before each test."""
        reset_tool_instances()
    
    def test_empty_url_list(self):
        """Should handle empty URL list."""
        result = fetch_pages([])
        
        assert result["total_attempted"] == 0
        assert result["successful"] == 0
        assert result["pages"] == []
    
    def test_limits_urls_to_20(self):
        """Should limit URLs to 20 max."""
        with patch('agents.site_investigation_tools._get_page_fetcher') as mock:
            mock_fetcher = MagicMock()
            mock.return_value = mock_fetcher
            
            from utils.page_fetcher import PageFetchResult, FetchedPage
            mock_result = PageFetchResult(
                pages=[],
                successful=0,
                failed=0,
                bot_protection_detected=False,
            )
            mock_fetcher.fetch_pages = AsyncMock(return_value=mock_result)
            
            # Pass 25 URLs
            urls = [f"https://example.com/page{i}" for i in range(25)]
            result = fetch_pages(urls)
            
            # Should only attempt 20
            assert result["total_attempted"] == 20


class TestAnalyzePageStructure:
    """Tests for analyze_page_structure tool."""
    
    def setup_method(self):
        """Reset tool instances before each test."""
        reset_tool_instances()
    
    def test_empty_html_content(self):
        """Should handle empty HTML content."""
        result = analyze_page_structure("https://example.com", "")
        
        assert "error" in result
        assert result["url"] == "https://example.com"
    
    def test_returns_dict_structure(self):
        """Should return proper dictionary structure."""
        html = """
        <html>
        <head><title>Test Page</title></head>
        <body><h1>Title</h1><p>Content</p></body>
        </html>
        """
        
        result = analyze_page_structure("https://example.com", html)
        
        assert "url" in result
        assert "headings" in result
        assert "metadata" in result
        assert "content_areas" in result
        assert "navigation_selectors" in result
        assert "stats" in result


class TestAnalyzePagePatterns:
    """Tests for analyze_page_patterns tool."""
    
    def test_empty_page_structures(self):
        """Should handle empty page structures list."""
        result = analyze_page_patterns([])
        
        assert result["total_pages_analyzed"] == 0
        assert result["common_classes"] == []
    
    def test_finds_common_patterns(self):
        """Should identify common patterns across pages."""
        structures = [
            {
                "url": "https://example.com/page1",
                "headings": {"h1": ["Title 1"]},
                "metadata": {"author": "John", "description": "Desc 1"},
                "content_areas": [
                    {"tag": "article", "classes": ["post-content", "main"]},
                ],
                "navigation_selectors": ["nav#main-nav"],
            },
            {
                "url": "https://example.com/page2",
                "headings": {"h1": ["Title 2"]},
                "metadata": {"author": None, "description": "Desc 2"},
                "content_areas": [
                    {"tag": "article", "classes": ["post-content"]},
                ],
                "navigation_selectors": ["nav#main-nav"],
            },
        ]
        
        result = analyze_page_patterns(structures)
        
        assert result["total_pages_analyzed"] == 2
        assert any(c["class"] == "post-content" for c in result["common_classes"])
        assert any(n["selector"] == "nav#main-nav" for n in result["common_navigation"])


class TestSelectSampleUrls:
    """Tests for select_sample_urls tool."""
    
    def test_prioritizes_seed_urls(self):
        """Should prioritize seed URLs over sitemap URLs."""
        seed_urls = ["https://example.com/seed1", "https://example.com/seed2"]
        sitemap_urls = ["https://example.com/page1", "https://example.com/page2"]
        
        result = select_sample_urls(
            "https://example.com",
            seed_urls,
            sitemap_urls,
            sample_count=3,
        )
        
        # First two should be seed URLs
        assert result[0] == "https://example.com/seed1"
        assert result[1] == "https://example.com/seed2"
    
    def test_falls_back_to_domain(self):
        """Should fall back to domain if no URLs provided."""
        result = select_sample_urls("example.com", None, [], sample_count=10)
        
        assert len(result) == 1
        assert result[0] == "https://example.com"
    
    def test_distributed_sampling(self):
        """Should use distributed sampling for large sitemap lists."""
        sitemap_urls = [f"https://example.com/page{i}" for i in range(100)]
        
        result = select_sample_urls(
            "https://example.com",
            None,
            sitemap_urls,
            sample_count=5,
        )
        
        # Should select 5 URLs distributed across the list
        assert len(result) == 5


class TestGenerateRecommendations:
    """Tests for generate_recommendations tool."""
    
    def test_empty_inputs(self):
        """Should handle empty inputs."""
        result = generate_recommendations(
            "https://example.com",
            {"rules": [], "accessible": True},
            [],
            {},
        )
        
        assert "crawl_rules" in result
        assert "extraction_rules" in result
        assert "challenges" in result
    
    def test_extracts_disallow_rules(self):
        """Should extract disallow rules from robots.txt."""
        robots_data = {
            "accessible": True,
            "rules": [
                {
                    "user_agent": "*",
                    "disallow": ["/admin/", "/private/"],
                    "allow": [],
                    "crawl_delay": None,
                }
            ],
        }
        
        result = generate_recommendations(
            "https://example.com",
            robots_data,
            [],
            {},
        )
        
        # Should have exclude_paths rule
        assert any(
            r["type"] == "exclude_paths" and "/admin/" in r["patterns"]
            for r in result["crawl_rules"]
        )


class TestAgnoAgentCreation:
    """Tests for Agno agent creation with tools."""
    
    def test_create_site_investigation_agent(self):
        """Should create an Agno agent with all tools."""
        from agents.site_investigation import create_site_investigation_agent
        from utils.config import Config
        
        original_key = Config.LLM_PROXY_API_KEY
        try:
            Config.LLM_PROXY_API_KEY = "test-key"
            
            agent = create_site_investigation_agent()
            
            assert agent.name == "SiteInvestigationAgent"
            assert len(agent.tools) == len(SITE_INVESTIGATION_TOOLS)
        finally:
            Config.LLM_PROXY_API_KEY = original_key
    
    def test_agent_has_instructions(self):
        """Agent should have investigation instructions."""
        from agents.site_investigation import (
            create_site_investigation_agent,
            SITE_INVESTIGATION_INSTRUCTIONS,
        )
        from utils.config import Config
        
        original_key = Config.LLM_PROXY_API_KEY
        try:
            Config.LLM_PROXY_API_KEY = "test-key"
            
            agent = create_site_investigation_agent()
            
            # Agent should have instructions
            assert agent.instructions is not None
            assert len(agent.instructions) > 0
        finally:
            Config.LLM_PROXY_API_KEY = original_key
