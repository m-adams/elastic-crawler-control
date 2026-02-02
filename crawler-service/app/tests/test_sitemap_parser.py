"""
Unit tests for sitemap parser.
"""

import pytest
from datetime import datetime
from utils.sitemap_parser import SitemapParser, SitemapURL, SitemapData
from xml.etree import ElementTree as ET


class TestSitemapParser:
    """Test cases for SitemapParser."""
    
    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return SitemapParser()
    
    def test_is_sitemap_index(self, parser):
        """Test detection of sitemap index vs URL set."""
        # Sitemap index
        index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap>
        <loc>https://example.com/sitemap1.xml</loc>
    </sitemap>
</sitemapindex>"""
        
        root = ET.fromstring(index_xml)
        assert parser._is_sitemap_index(root)
        
        # URL set
        urlset_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://example.com/page1</loc>
    </url>
</urlset>"""
        
        root = ET.fromstring(urlset_xml)
        assert not parser._is_sitemap_index(root)
    
    def test_parse_urlset(self, parser):
        """Test parsing a URL set sitemap."""
        urlset_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://example.com/page1</loc>
        <lastmod>2024-01-15</lastmod>
        <changefreq>weekly</changefreq>
        <priority>0.8</priority>
    </url>
    <url>
        <loc>https://example.com/page2</loc>
        <lastmod>2024-01-20</lastmod>
    </url>
</urlset>"""
        
        root = ET.fromstring(urlset_xml)
        result = parser._parse_urlset("https://example.com/sitemap.xml", root)
        
        assert len(result.urls) == 2
        assert result.urls[0].loc == "https://example.com/page1"
        assert result.urls[0].changefreq == "weekly"
        assert result.urls[0].priority == 0.8
        assert result.urls[1].loc == "https://example.com/page2"
    
    def test_parse_sitemap_index(self, parser):
        """Test parsing a sitemap index."""
        index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap>
        <loc>https://example.com/sitemap1.xml</loc>
    </sitemap>
    <sitemap>
        <loc>https://example.com/sitemap2.xml</loc>
    </sitemap>
</sitemapindex>"""
        
        root = ET.fromstring(index_xml)
        result = parser._parse_sitemap_index("https://example.com/sitemap.xml", root)
        
        assert len(result.nested_sitemaps) == 2
        assert "https://example.com/sitemap1.xml" in result.nested_sitemaps
        assert "https://example.com/sitemap2.xml" in result.nested_sitemaps
    
    def test_parse_datetime(self, parser):
        """Test datetime parsing."""
        # Test various formats
        assert parser._parse_datetime("2024-01-15") is not None
        assert parser._parse_datetime("2024-01-15T10:30:00") is not None
        assert parser._parse_datetime("2024-01-15T10:30:00Z") is not None
        
        # Invalid format
        assert parser._parse_datetime("invalid") is None
    
    def test_parse_without_namespace(self, parser):
        """Test parsing sitemap without namespace."""
        # Some sitemaps don't include the namespace
        urlset_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset>
    <url>
        <loc>https://example.com/page1</loc>
        <lastmod>2024-01-15</lastmod>
    </url>
</urlset>"""
        
        root = ET.fromstring(urlset_xml)
        result = parser._parse_urlset("https://example.com/sitemap.xml", root)
        
        assert len(result.urls) == 1
        assert result.urls[0].loc == "https://example.com/page1"


@pytest.mark.asyncio
class TestSitemapParserAsync:
    """Async test cases for SitemapParser."""
    
    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return SitemapParser()
    
    async def test_fetch_invalid_url(self, parser):
        """Test handling of invalid sitemap URL."""
        result = await parser.fetch_and_parse("https://example.com/nonexistent.xml")
        
        assert isinstance(result, SitemapData)
        assert not result.accessible
        assert result.error is not None
