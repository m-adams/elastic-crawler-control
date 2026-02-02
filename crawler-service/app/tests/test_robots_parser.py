"""
Unit tests for robots.txt parser.
"""

import pytest
from utils.robots_parser import RobotsParser, RobotsData, RobotsRule


class TestRobotsParser:
    """Test cases for RobotsParser."""
    
    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return RobotsParser()
    
    def test_parse_simple_robots(self, parser):
        """Test parsing a simple robots.txt file."""
        content = """
User-agent: *
Disallow: /admin/
Disallow: /private/
Allow: /public/

Sitemap: https://example.com/sitemap.xml
"""
        rules = parser._parse_rules(content)
        
        assert len(rules) == 1
        assert rules[0].user_agent == "*"
        assert "/admin/" in rules[0].disallow
        assert "/private/" in rules[0].disallow
        assert "/public/" in rules[0].allow
    
    def test_parse_multiple_user_agents(self, parser):
        """Test parsing multiple user-agent sections."""
        content = """
User-agent: Googlebot
Disallow: /private/
Crawl-delay: 1

User-agent: *
Disallow: /admin/
"""
        rules = parser._parse_rules(content)
        
        assert len(rules) == 2
        assert rules[0].user_agent == "Googlebot"
        assert rules[0].crawl_delay == 1.0
        assert rules[1].user_agent == "*"
    
    def test_extract_sitemaps(self, parser):
        """Test extracting sitemap URLs."""
        content = """
User-agent: *
Disallow: /admin/

Sitemap: https://example.com/sitemap.xml
Sitemap: https://example.com/sitemap-news.xml
"""
        sitemaps = parser._extract_sitemaps(content)
        
        assert len(sitemaps) == 2
        assert "https://example.com/sitemap.xml" in sitemaps
        assert "https://example.com/sitemap-news.xml" in sitemaps
    
    def test_is_allowed_simple(self, parser):
        """Test URL allow/disallow checking."""
        robots_data = RobotsData(
            raw_content="",
            rules=[
                RobotsRule(
                    user_agent="*",
                    allow=[],
                    disallow=["/admin/", "/private/"],
                )
            ],
            sitemaps=[],
            accessible=True,
        )
        
        assert parser.is_allowed("https://example.com/public/page", robots_data)
        assert not parser.is_allowed("https://example.com/admin/users", robots_data)
        assert not parser.is_allowed("https://example.com/private/data", robots_data)
    
    def test_is_allowed_with_wildcards(self, parser):
        """Test pattern matching with wildcards."""
        robots_data = RobotsData(
            raw_content="",
            rules=[
                RobotsRule(
                    user_agent="*",
                    allow=[],
                    disallow=["/*.pdf$", "/temp*"],
                )
            ],
            sitemaps=[],
            accessible=True,
        )
        
        assert not parser.is_allowed("https://example.com/document.pdf", robots_data)
        assert parser.is_allowed("https://example.com/document.html", robots_data)
        assert not parser.is_allowed("https://example.com/temp-files/", robots_data)
    
    def test_matches_pattern(self, parser):
        """Test pattern matching logic."""
        assert parser._matches_pattern("/admin/users", "/admin/")
        assert parser._matches_pattern("/document.pdf", "/*.pdf$")
        assert not parser._matches_pattern("/document.pdf.bak", "/*.pdf$")
        assert parser._matches_pattern("/temp-files/", "/temp*")
        assert parser._matches_pattern("/a/b/c", "/a/*/c")


@pytest.mark.asyncio
class TestRobotsParserAsync:
    """Async test cases for RobotsParser."""
    
    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return RobotsParser()
    
    async def test_fetch_missing_robots(self, parser):
        """Test handling of missing robots.txt (404)."""
        # This will likely 404 or fail, which is expected
        result = await parser.fetch_and_parse("https://httpbin.org/robots.txt")
        
        # Should handle gracefully
        assert isinstance(result, RobotsData)
