"""
HTML structure analyzer for site investigation.

Analyzes HTML pages to identify:
- Heading structure (h1-h6)
- Main content areas
- Navigation elements
- Metadata (title, description, author, date)
- Common patterns across pages
"""

from collections import Counter
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup, Tag


@dataclass
class HeadingStructure:
    """Structure of headings on a page."""
    
    h1: list[str]
    h2: list[str]
    h3: list[str]
    h4: list[str]
    h5: list[str]
    h6: list[str]
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "h1": self.h1,
            "h2": self.h2,
            "h3": self.h3,
            "h4": self.h4,
            "h5": self.h5,
            "h6": self.h6,
        }


@dataclass
class PageMetadata:
    """Metadata extracted from a page."""
    
    title: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[str] = None
    modified_date: Optional[str] = None
    keywords: list[str] = None
    og_type: Optional[str] = None
    og_image: Optional[str] = None
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []


@dataclass
class ContentArea:
    """A content area identified on the page."""
    
    selector: str
    tag: str
    classes: list[str]
    text_length: int
    has_images: bool
    has_links: bool


@dataclass
class PageStructure:
    """Complete structure analysis of a page."""
    
    url: str
    headings: HeadingStructure
    metadata: PageMetadata
    content_areas: list[ContentArea]
    navigation_selectors: list[str]
    total_links: int
    total_images: int
    text_length: int


class HTMLAnalyzer:
    """Analyzes HTML structure to identify patterns."""
    
    def __init__(self, parser: str = "lxml"):
        """
        Initialize HTML analyzer.
        
        Args:
            parser: BeautifulSoup parser to use
        """
        self.parser = parser
    
    def analyze_page(self, url: str, html_content: str) -> PageStructure:
        """
        Analyze a single page's HTML structure.
        
        Args:
            url: Page URL
            html_content: Raw HTML content
            
        Returns:
            Structured analysis of the page
        """
        soup = BeautifulSoup(html_content, self.parser)
        
        return PageStructure(
            url=url,
            headings=self._extract_headings(soup),
            metadata=self._extract_metadata(soup),
            content_areas=self._identify_content_areas(soup),
            navigation_selectors=self._identify_navigation(soup),
            total_links=len(soup.find_all("a")),
            total_images=len(soup.find_all("img")),
            text_length=len(soup.get_text(strip=True)),
        )
    
    def _extract_headings(self, soup: BeautifulSoup) -> HeadingStructure:
        """
        Extract all headings from the page.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            Heading structure
        """
        return HeadingStructure(
            h1=[h.get_text(strip=True) for h in soup.find_all("h1")],
            h2=[h.get_text(strip=True) for h in soup.find_all("h2")],
            h3=[h.get_text(strip=True) for h in soup.find_all("h3")],
            h4=[h.get_text(strip=True) for h in soup.find_all("h4")],
            h5=[h.get_text(strip=True) for h in soup.find_all("h5")],
            h6=[h.get_text(strip=True) for h in soup.find_all("h6")],
        )
    
    def _extract_metadata(self, soup: BeautifulSoup) -> PageMetadata:
        """
        Extract metadata from page head.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            Page metadata
        """
        metadata = PageMetadata()
        
        # Title
        title_tag = soup.find("title")
        if title_tag:
            metadata.title = title_tag.get_text(strip=True)
        
        # Meta tags
        meta_tags = soup.find_all("meta")
        for meta in meta_tags:
            name = meta.get("name", "").lower()
            property_name = meta.get("property", "").lower()
            content = meta.get("content", "")
            
            if not content:
                continue
            
            # Standard meta tags
            if name == "description":
                metadata.description = content
            elif name == "author":
                metadata.author = content
            elif name == "keywords":
                metadata.keywords = [k.strip() for k in content.split(",")]
            elif name == "date" or name == "published":
                metadata.published_date = content
            elif name == "last-modified":
                metadata.modified_date = content
            
            # Open Graph tags
            elif property_name == "og:type":
                metadata.og_type = content
            elif property_name == "og:image":
                metadata.og_image = content
            
            # Article tags
            elif property_name == "article:published_time":
                metadata.published_date = content
            elif property_name == "article:modified_time":
                metadata.modified_date = content
            elif property_name == "article:author":
                metadata.author = content
        
        return metadata
    
    def _identify_content_areas(self, soup: BeautifulSoup) -> list[ContentArea]:
        """
        Identify main content areas on the page.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            List of identified content areas
        """
        content_areas = []
        
        # Common content selectors
        content_selectors = [
            ("main", None),
            ("article", None),
            ("div", ["content", "main-content", "post", "article", "entry"]),
            ("section", ["content", "main", "article"]),
        ]
        
        for tag_name, class_list in content_selectors:
            if class_list:
                for class_name in class_list:
                    elements = soup.find_all(tag_name, class_=lambda x: x and class_name in x.lower() if x else False)
                    for elem in elements:
                        content_areas.append(self._analyze_content_area(elem))
            else:
                elements = soup.find_all(tag_name)
                for elem in elements:
                    content_areas.append(self._analyze_content_area(elem))
        
        # Sort by text length (largest first)
        content_areas.sort(key=lambda x: x.text_length, reverse=True)
        
        # Return top 5 content areas
        return content_areas[:5]
    
    def _analyze_content_area(self, element: Tag) -> ContentArea:
        """
        Analyze a single content area element.
        
        Args:
            element: BeautifulSoup Tag element
            
        Returns:
            Content area analysis
        """
        text = element.get_text(strip=True)
        classes = element.get("class", [])
        
        return ContentArea(
            selector=self._generate_selector(element),
            tag=element.name,
            classes=classes if isinstance(classes, list) else [classes],
            text_length=len(text),
            has_images=len(element.find_all("img")) > 0,
            has_links=len(element.find_all("a")) > 0,
        )
    
    def _generate_selector(self, element: Tag) -> str:
        """
        Generate a CSS selector for an element.
        
        Args:
            element: BeautifulSoup Tag element
            
        Returns:
            CSS selector string
        """
        tag = element.name
        
        # Use ID if available
        elem_id = element.get("id")
        if elem_id:
            return f"{tag}#{elem_id}"
        
        # Use first class if available
        classes = element.get("class", [])
        if classes:
            if isinstance(classes, list):
                return f"{tag}.{classes[0]}"
            else:
                return f"{tag}.{classes}"
        
        return tag
    
    def _identify_navigation(self, soup: BeautifulSoup) -> list[str]:
        """
        Identify navigation elements.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            List of navigation selectors
        """
        nav_selectors = []
        
        # Find nav tags
        nav_elements = soup.find_all("nav")
        for nav in nav_elements:
            nav_selectors.append(self._generate_selector(nav))
        
        # Find elements with navigation-related classes
        nav_classes = ["nav", "navigation", "menu", "header-menu", "navbar"]
        for nav_class in nav_classes:
            elements = soup.find_all(class_=lambda x: x and nav_class in x.lower() if x else False)
            for elem in elements:
                selector = self._generate_selector(elem)
                if selector not in nav_selectors:
                    nav_selectors.append(selector)
        
        return nav_selectors
    
    def analyze_patterns(self, structures: list[PageStructure]) -> dict:
        """
        Analyze patterns across multiple pages.
        
        Args:
            structures: List of page structures
            
        Returns:
            Pattern analysis including common elements
        """
        if not structures:
            return {}
        
        # Analyze common classes
        all_classes = []
        for struct in structures:
            for area in struct.content_areas:
                all_classes.extend(area.classes)
        
        class_counter = Counter(all_classes)
        common_classes = class_counter.most_common(10)
        
        # Analyze common navigation patterns
        all_nav_selectors = []
        for struct in structures:
            all_nav_selectors.extend(struct.navigation_selectors)
        
        nav_counter = Counter(all_nav_selectors)
        common_nav = nav_counter.most_common(5)
        
        # Analyze heading patterns
        h1_counts = [len(struct.headings.h1) for struct in structures]
        avg_h1_count = sum(h1_counts) / len(h1_counts) if h1_counts else 0
        
        # Analyze content area patterns
        content_tags = []
        for struct in structures:
            for area in struct.content_areas:
                content_tags.append(area.tag)
        
        tag_counter = Counter(content_tags)
        common_content_tags = tag_counter.most_common(5)
        
        # Analyze metadata patterns
        has_author = sum(1 for s in structures if s.metadata.author) / len(structures)
        has_date = sum(1 for s in structures if s.metadata.published_date) / len(structures)
        has_description = sum(1 for s in structures if s.metadata.description) / len(structures)
        
        return {
            "total_pages_analyzed": len(structures),
            "common_classes": [{"class": cls, "count": count} for cls, count in common_classes],
            "common_navigation": [{"selector": sel, "count": count} for sel, count in common_nav],
            "common_content_tags": [{"tag": tag, "count": count} for tag, count in common_content_tags],
            "heading_patterns": {
                "avg_h1_count": avg_h1_count,
            },
            "metadata_coverage": {
                "has_author": f"{has_author * 100:.1f}%",
                "has_date": f"{has_date * 100:.1f}%",
                "has_description": f"{has_description * 100:.1f}%",
            },
        }
