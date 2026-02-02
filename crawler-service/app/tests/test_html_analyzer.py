"""
Unit tests for HTML analyzer.
"""

import pytest
from utils.html_analyzer import HTMLAnalyzer, PageStructure, HeadingStructure


class TestHTMLAnalyzer:
    """Test cases for HTMLAnalyzer."""
    
    @pytest.fixture
    def analyzer(self):
        """Create an analyzer instance."""
        return HTMLAnalyzer(parser="html.parser")  # Use built-in parser for tests
    
    def test_extract_headings(self, analyzer):
        """Test heading extraction."""
        html = """
        <html>
        <body>
            <h1>Main Title</h1>
            <h2>Section 1</h2>
            <h3>Subsection 1.1</h3>
            <h2>Section 2</h2>
        </body>
        </html>
        """
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        headings = analyzer._extract_headings(soup)
        
        assert len(headings.h1) == 1
        assert headings.h1[0] == "Main Title"
        assert len(headings.h2) == 2
        assert "Section 1" in headings.h2
        assert len(headings.h3) == 1
    
    def test_extract_metadata(self, analyzer):
        """Test metadata extraction."""
        html = """
        <html>
        <head>
            <title>Test Page</title>
            <meta name="description" content="This is a test page">
            <meta name="author" content="John Doe">
            <meta name="keywords" content="test, page, example">
            <meta property="og:type" content="article">
        </head>
        <body></body>
        </html>
        """
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        metadata = analyzer._extract_metadata(soup)
        
        assert metadata.title == "Test Page"
        assert metadata.description == "This is a test page"
        assert metadata.author == "John Doe"
        assert "test" in metadata.keywords
        assert metadata.og_type == "article"
    
    def test_identify_content_areas(self, analyzer):
        """Test content area identification."""
        html = """
        <html>
        <body>
            <nav>Navigation</nav>
            <main>
                <article>
                    <h1>Article Title</h1>
                    <p>Article content with lots of text here.</p>
                </article>
            </main>
            <div class="sidebar">Sidebar</div>
        </body>
        </html>
        """
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        content_areas = analyzer._identify_content_areas(soup)
        
        assert len(content_areas) > 0
        # Main content should be identified
        assert any("main" in area.selector.lower() or "article" in area.selector.lower() 
                  for area in content_areas)
    
    def test_identify_navigation(self, analyzer):
        """Test navigation element identification."""
        html = """
        <html>
        <body>
            <nav id="main-nav">
                <ul>
                    <li><a href="/">Home</a></li>
                    <li><a href="/about">About</a></li>
                </ul>
            </nav>
            <div class="navbar">Another nav</div>
        </body>
        </html>
        """
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        nav_selectors = analyzer._identify_navigation(soup)
        
        assert len(nav_selectors) > 0
        assert any("nav" in sel for sel in nav_selectors)
    
    def test_analyze_page(self, analyzer):
        """Test full page analysis."""
        html = """
        <html>
        <head>
            <title>Test Page</title>
            <meta name="description" content="Test description">
        </head>
        <body>
            <nav>Navigation</nav>
            <main>
                <h1>Main Title</h1>
                <article>
                    <h2>Article Title</h2>
                    <p>Article content goes here.</p>
                    <img src="image.jpg" alt="Test image">
                    <a href="/link">Link</a>
                </article>
            </main>
        </body>
        </html>
        """
        
        result = analyzer.analyze_page("https://example.com/page", html)
        
        assert isinstance(result, PageStructure)
        assert result.url == "https://example.com/page"
        assert len(result.headings.h1) > 0
        assert result.metadata.title == "Test Page"
        assert result.total_links > 0
        assert result.total_images > 0
        assert result.text_length > 0
    
    def test_analyze_patterns(self, analyzer):
        """Test pattern analysis across multiple pages."""
        html1 = """
        <html>
        <body>
            <article class="post-content">
                <h1>Title 1</h1>
                <p>Content 1</p>
            </article>
        </body>
        </html>
        """
        
        html2 = """
        <html>
        <body>
            <article class="post-content">
                <h1>Title 2</h1>
                <p>Content 2</p>
            </article>
        </body>
        </html>
        """
        
        struct1 = analyzer.analyze_page("https://example.com/page1", html1)
        struct2 = analyzer.analyze_page("https://example.com/page2", html2)
        
        patterns = analyzer.analyze_patterns([struct1, struct2])
        
        assert patterns["total_pages_analyzed"] == 2
        assert "common_classes" in patterns
        assert "common_content_tags" in patterns
        # Should identify "post-content" as common class
        assert any(c["class"] == "post-content" for c in patterns["common_classes"])
