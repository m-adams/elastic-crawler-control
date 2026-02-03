"""
Site Directory API - Curated list of demo sites with crawlability status.

Provides a "phonebook" of sites covering different use cases for demos,
with pre-checked viability status for Open Crawler.

Endpoints:
- GET /api/sites/directory - Get full site directory
- GET /api/sites/search?q=query - Search sites by name/category
- POST /api/sites/check/{site_id} - Re-check a specific site
"""

from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/sites", tags=["sites"])


# =============================================================================
# Site Directory Data
# =============================================================================

class SiteCategory(str, Enum):
    """Categories for demo sites."""
    NEWS = "news"
    TECH_BLOG = "tech_blog"
    DOCUMENTATION = "documentation"
    ECOMMERCE = "ecommerce"
    DEVELOPER = "developer"
    REFERENCE = "reference"
    SOCIAL = "social"
    GOVERNMENT = "government"
    EDUCATION = "education"


class CrawlStatus(str, Enum):
    """Crawl viability status."""
    WORKS = "works"           # Confirmed working with Open Crawler
    PARTIAL = "partial"       # Works but may have limitations
    BLOCKED = "blocked"       # Blocked by bot protection
    UNTESTED = "untested"     # Not yet tested


class SiteEntry(BaseModel):
    """A site in the directory."""
    id: str
    name: str
    url: str
    category: SiteCategory
    description: str
    status: CrawlStatus
    status_note: Optional[str] = None
    content_type: str = Field(description="Suggested content type for config generation")
    tags: List[str] = Field(default_factory=list)
    last_checked: Optional[str] = None


# Curated site directory
SITE_DIRECTORY: List[Dict[str, Any]] = [
    # News Sites
    {
        "id": "bbc-news",
        "name": "BBC News",
        "url": "https://www.bbc.co.uk/news",
        "category": SiteCategory.NEWS,
        "description": "UK's national broadcaster - news articles and features",
        "status": CrawlStatus.WORKS,
        "status_note": "Server-rendered content, works great",
        "content_type": "blog",
        "tags": ["news", "uk", "articles", "server-rendered"],
        "last_checked": "2026-02-02",
    },
    {
        "id": "guardian",
        "name": "The Guardian",
        "url": "https://www.theguardian.com/uk",
        "category": SiteCategory.NEWS,
        "description": "International news, opinion and features",
        "status": CrawlStatus.WORKS,
        "status_note": "Fast, clean extraction",
        "content_type": "blog",
        "tags": ["news", "uk", "international", "articles"],
        "last_checked": "2026-02-02",
    },
    {
        "id": "nytimes",
        "name": "NY Times",
        "url": "https://www.nytimes.com",
        "category": SiteCategory.NEWS,
        "description": "American newspaper of record",
        "status": CrawlStatus.WORKS,
        "status_note": "Server-rendered, works well",
        "content_type": "blog",
        "tags": ["news", "us", "articles", "premium"],
        "last_checked": "2026-02-02",
    },
    {
        "id": "hacker-news",
        "name": "Hacker News",
        "url": "https://news.ycombinator.com",
        "category": SiteCategory.NEWS,
        "description": "Tech news and discussion from Y Combinator",
        "status": CrawlStatus.WORKS,
        "status_note": "Simple HTML, very fast",
        "content_type": "blog",
        "tags": ["tech", "news", "discussion", "simple"],
        "last_checked": "2026-02-02",
    },
    {
        "id": "reuters",
        "name": "Reuters",
        "url": "https://www.reuters.com",
        "category": SiteCategory.NEWS,
        "description": "International news agency",
        "status": CrawlStatus.BLOCKED,
        "status_note": "DataDome bot protection - use Firecrawl",
        "content_type": "blog",
        "tags": ["news", "international", "blocked"],
        "last_checked": "2026-02-02",
    },
    
    # Tech Blogs
    {
        "id": "elastic-blog",
        "name": "Elastic Blog",
        "url": "https://www.elastic.co/blog",
        "category": SiteCategory.TECH_BLOG,
        "description": "Official Elastic blog - search, observability, security",
        "status": CrawlStatus.WORKS,
        "status_note": "No issues, great for demos",
        "content_type": "blog",
        "tags": ["tech", "elasticsearch", "observability", "official"],
        "last_checked": "2026-02-02",
    },
    {
        "id": "shopify-blog",
        "name": "Shopify Blog",
        "url": "https://www.shopify.com/blog",
        "category": SiteCategory.TECH_BLOG,
        "description": "E-commerce tips, business advice, and entrepreneurship",
        "status": CrawlStatus.WORKS,
        "status_note": "Works despite some bot protection headers",
        "content_type": "blog",
        "tags": ["ecommerce", "business", "entrepreneurship"],
        "last_checked": "2026-02-02",
    },
    {
        "id": "medium",
        "name": "Medium",
        "url": "https://medium.com",
        "category": SiteCategory.TECH_BLOG,
        "description": "Publishing platform for blogs and articles",
        "status": CrawlStatus.WORKS,
        "status_note": "Works, but has some JS features",
        "content_type": "blog",
        "tags": ["blog", "publishing", "articles"],
        "last_checked": "2026-02-02",
    },
    {
        "id": "techcrunch",
        "name": "TechCrunch",
        "url": "https://www.techcrunch.com",
        "category": SiteCategory.TECH_BLOG,
        "description": "Startup and technology news",
        "status": CrawlStatus.BLOCKED,
        "status_note": "Bot protection - use Firecrawl",
        "content_type": "blog",
        "tags": ["tech", "startups", "blocked"],
        "last_checked": "2026-02-02",
    },
    
    # Documentation
    {
        "id": "wikipedia",
        "name": "Wikipedia",
        "url": "https://www.wikipedia.org",
        "category": SiteCategory.REFERENCE,
        "description": "Free online encyclopedia",
        "status": CrawlStatus.WORKS,
        "status_note": "Clean HTML, fast crawling",
        "content_type": "documentation",
        "tags": ["reference", "encyclopedia", "knowledge"],
        "last_checked": "2026-02-02",
    },
    {
        "id": "python-docs",
        "name": "Python Docs",
        "url": "https://docs.python.org",
        "category": SiteCategory.DOCUMENTATION,
        "description": "Official Python documentation",
        "status": CrawlStatus.PARTIAL,
        "status_note": "Homepage redirects - use specific version URLs",
        "content_type": "documentation",
        "tags": ["python", "programming", "docs"],
        "last_checked": "2026-02-02",
    },
    {
        "id": "mdn",
        "name": "MDN Web Docs",
        "url": "https://developer.mozilla.org",
        "category": SiteCategory.DOCUMENTATION,
        "description": "Web technology documentation by Mozilla",
        "status": CrawlStatus.PARTIAL,
        "status_note": "May need specific URL paths",
        "content_type": "documentation",
        "tags": ["web", "javascript", "html", "css", "docs"],
        "last_checked": "2026-02-02",
    },
    
    # Developer Platforms
    {
        "id": "github",
        "name": "GitHub",
        "url": "https://github.com",
        "category": SiteCategory.DEVELOPER,
        "description": "Code hosting and collaboration platform",
        "status": CrawlStatus.WORKS,
        "status_note": "Public repos work well",
        "content_type": "documentation",
        "tags": ["code", "git", "developer", "repos"],
        "last_checked": "2026-02-02",
    },
    {
        "id": "npm",
        "name": "npm",
        "url": "https://www.npmjs.com",
        "category": SiteCategory.DEVELOPER,
        "description": "JavaScript package registry",
        "status": CrawlStatus.WORKS,
        "status_note": "Package pages work well",
        "content_type": "documentation",
        "tags": ["javascript", "packages", "nodejs"],
        "last_checked": "2026-02-02",
    },
    {
        "id": "stackoverflow",
        "name": "Stack Overflow",
        "url": "https://stackoverflow.com",
        "category": SiteCategory.DEVELOPER,
        "description": "Q&A for programmers",
        "status": CrawlStatus.BLOCKED,
        "status_note": "Bot protection - use Firecrawl",
        "content_type": "documentation",
        "tags": ["qa", "programming", "blocked"],
        "last_checked": "2026-02-02",
    },
    
    # E-commerce (examples)
    {
        "id": "elastic-pricing",
        "name": "Elastic Pricing",
        "url": "https://www.elastic.co/pricing",
        "category": SiteCategory.ECOMMERCE,
        "description": "Elastic Cloud pricing and plans",
        "status": CrawlStatus.WORKS,
        "status_note": "Good for product/pricing extraction",
        "content_type": "ecommerce",
        "tags": ["pricing", "products", "elastic"],
        "last_checked": "2026-02-02",
    },
]


# =============================================================================
# Response Models
# =============================================================================

class DirectoryResponse(BaseModel):
    """Full site directory response."""
    sites: List[SiteEntry]
    total: int
    categories: List[str]
    stats: Dict[str, int]


class SearchResponse(BaseModel):
    """Search results response."""
    query: str
    results: List[SiteEntry]
    total: int


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/directory", response_model=DirectoryResponse)
async def get_directory(
    category: Optional[SiteCategory] = Query(None, description="Filter by category"),
    status: Optional[CrawlStatus] = Query(None, description="Filter by status"),
) -> DirectoryResponse:
    """
    Get the full site directory.
    
    Optionally filter by category or crawl status.
    
    Returns:
        DirectoryResponse with sites, categories, and stats
    """
    sites = SITE_DIRECTORY
    
    # Apply filters
    if category:
        sites = [s for s in sites if s["category"] == category]
    if status:
        sites = [s for s in sites if s["status"] == status]
    
    # Convert to SiteEntry models
    site_entries = [SiteEntry(**s) for s in sites]
    
    # Calculate stats
    all_sites = SITE_DIRECTORY
    stats = {
        "total": len(all_sites),
        "works": len([s for s in all_sites if s["status"] == CrawlStatus.WORKS]),
        "partial": len([s for s in all_sites if s["status"] == CrawlStatus.PARTIAL]),
        "blocked": len([s for s in all_sites if s["status"] == CrawlStatus.BLOCKED]),
    }
    
    # Get unique categories
    categories = list(set(s["category"].value for s in all_sites))
    
    return DirectoryResponse(
        sites=site_entries,
        total=len(site_entries),
        categories=categories,
        stats=stats,
    )


@router.get("/search", response_model=SearchResponse)
async def search_sites(
    q: str = Query(..., min_length=1, description="Search query"),
) -> SearchResponse:
    """
    Search sites by name, URL, description, or tags.
    
    Args:
        q: Search query string
        
    Returns:
        SearchResponse with matching sites
    """
    query = q.lower().strip()
    
    results = []
    for site in SITE_DIRECTORY:
        # Search in multiple fields
        searchable = " ".join([
            site["name"].lower(),
            site["url"].lower(),
            site["description"].lower(),
            site["category"].value.lower(),
            " ".join(site.get("tags", [])).lower(),
        ])
        
        if query in searchable:
            results.append(SiteEntry(**site))
    
    return SearchResponse(
        query=q,
        results=results,
        total=len(results),
    )


@router.get("/suggest")
async def suggest_sites(
    url: str = Query(..., description="Partial URL being typed"),
    limit: int = Query(5, ge=1, le=10, description="Max suggestions"),
) -> List[SiteEntry]:
    """
    Suggest sites as user types a URL.
    
    Matches against site URLs and names for autocomplete.
    
    Args:
        url: Partial URL being typed
        limit: Maximum number of suggestions
        
    Returns:
        List of matching SiteEntry suggestions
    """
    query = url.lower().strip()
    
    # Remove common prefixes for matching
    for prefix in ["https://", "http://", "www."]:
        if query.startswith(prefix):
            query = query[len(prefix):]
    
    suggestions = []
    for site in SITE_DIRECTORY:
        site_url = site["url"].lower()
        site_name = site["name"].lower()
        
        # Remove prefixes from site URL too
        clean_url = site_url
        for prefix in ["https://", "http://", "www."]:
            clean_url = clean_url.replace(prefix, "")
        
        # Match if query is in URL or name
        if query in clean_url or query in site_name:
            suggestions.append(SiteEntry(**site))
            if len(suggestions) >= limit:
                break
    
    return suggestions


@router.get("/{site_id}")
async def get_site(site_id: str) -> SiteEntry:
    """
    Get a specific site by ID.
    
    Args:
        site_id: The site identifier
        
    Returns:
        SiteEntry for the site
        
    Raises:
        404 if site not found
    """
    from fastapi import HTTPException
    
    for site in SITE_DIRECTORY:
        if site["id"] == site_id:
            return SiteEntry(**site)
    
    raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
