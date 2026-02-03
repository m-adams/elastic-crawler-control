"""
Domain Preflight & Deep-Check API endpoints.

Lightweight validation endpoints that run BEFORE engaging the LLM workflow.
These checks save LLM costs and provide instant feedback to users.

Endpoints:
- POST /api/domain/preflight - Fast checks (DNS, HTTP, robots.txt) ~2-3s
- POST /api/domain/deep-check - Thorough checks (urltest, bot detection) ~5-10s

When bot protection is detected, recommends Firecrawl as an alternative
with appropriate cost warnings.
"""

import asyncio
import re
import socket
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field
from fastapi import APIRouter

from utils.crawler_client import get_crawler_client, CrawlerClient
from utils.logging import get_logger

logger = get_logger(__name__)


router = APIRouter(prefix="/api/domain", tags=["domain"])


# =============================================================================
# Constants
# =============================================================================

# Firecrawl info for bot-protected sites
FIRECRAWL_INFO = {
    "name": "Firecrawl",
    "url": "https://firecrawl.dev",
    "description": "Firecrawl can handle JavaScript-rendered sites and bypass some bot protection",
    "pricing_note": "Firecrawl is a paid service. Check their pricing at https://firecrawl.dev/pricing",
    "when_to_use": [
        "Site requires JavaScript rendering",
        "Cloudflare or similar bot protection detected",
        "CAPTCHA challenges present",
        "Open Crawler is blocked but content is accessible via browser",
    ],
}

# Known bot protection signatures
BOT_PROTECTION_SIGNATURES = {
    "cloudflare": {
        "headers": ["cf-ray", "cf-cache-status", "cf-request-id"],
        "body_patterns": [
            r"cloudflare",
            r"cf-browser-verification",
            r"checking your browser",
            r"ray id:",
            r"__cf_chl_opt",
        ],
        "name": "Cloudflare",
    },
    "akamai": {
        "headers": ["x-akamai-transformed", "akamai-grn"],
        "body_patterns": [r"akamai", r"_abck"],
        "name": "Akamai Bot Manager",
    },
    "imperva": {
        "headers": ["x-iinfo"],
        "body_patterns": [r"incapsula", r"imperva"],
        "name": "Imperva/Incapsula",
    },
    "datadome": {
        "headers": ["x-datadome"],
        "body_patterns": [r"datadome"],
        "name": "DataDome",
    },
    "perimeterx": {
        "headers": ["x-px-"],
        "body_patterns": [r"perimeterx", r"_pxhd"],
        "name": "PerimeterX",
    },
}

# JavaScript-required indicators
JS_REQUIRED_PATTERNS = [
    r"<noscript>.*enable javascript",
    r"javascript is required",
    r"please enable javascript",
    r"this site requires javascript",
    r"<div id=\"?root\"?>\s*</div>",  # Empty React root
    r"<div id=\"?app\"?>\s*</div>",   # Empty Vue/other app root
]


# =============================================================================
# Request/Response Models
# =============================================================================

class IssueSeverity(str, Enum):
    """Severity levels for preflight issues."""
    ERROR = "error"      # Blocks generation
    WARNING = "warning"  # Proceed with caution
    INFO = "info"        # Informational


class PreflightIssue(BaseModel):
    """A single issue found during preflight checks."""
    severity: IssueSeverity
    code: str
    message: str
    suggestion: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class RobotsTxtInfo(BaseModel):
    """Information from robots.txt analysis."""
    exists: bool = False
    allows_crawling: bool = True
    sitemap_urls: List[str] = Field(default_factory=list)
    blocked_paths: List[str] = Field(default_factory=list)
    crawl_delay: Optional[int] = None
    raw_content: Optional[str] = None


class BotProtectionInfo(BaseModel):
    """Information about detected bot protection."""
    detected: bool = False
    provider: Optional[str] = None
    provider_name: Optional[str] = None
    confidence: str = "none"  # none, low, medium, high
    indicators: List[str] = Field(default_factory=list)


class FirecrawlRecommendation(BaseModel):
    """Recommendation to use Firecrawl."""
    recommended: bool = False
    reason: Optional[str] = None
    firecrawl_url: str = FIRECRAWL_INFO["url"]
    pricing_note: str = FIRECRAWL_INFO["pricing_note"]
    when_to_use: List[str] = Field(default_factory=list)


class PreflightRequest(BaseModel):
    """Request for domain preflight check."""
    url: str = Field(..., description="URL to check (e.g., 'https://example.com')")
    check_robots: bool = Field(default=True, description="Check robots.txt")


class PreflightResponse(BaseModel):
    """Response from preflight checks."""
    # Input
    original_url: str
    normalized_url: str
    domain: str
    
    # Basic checks
    url_valid: bool = False
    dns_resolves: bool = False
    http_reachable: bool = False
    https_available: bool = False
    
    # Response info
    final_url: Optional[str] = None
    status_code: Optional[int] = None
    response_time_ms: Optional[int] = None
    redirect_chain: List[str] = Field(default_factory=list)
    
    # robots.txt
    robots_txt: Optional[RobotsTxtInfo] = None
    
    # Issues found
    issues: List[PreflightIssue] = Field(default_factory=list)
    
    # Overall status
    viable_for_crawling: bool = False
    error: Optional[str] = None


class DeepCheckRequest(BaseModel):
    """Request for deep domain check."""
    url: str = Field(..., description="URL to check")
    sample_path: Optional[str] = Field(
        default=None, 
        description="Specific path to test (e.g., '/products/item-1')"
    )


class DeepCheckResponse(BaseModel):
    """Response from deep checks."""
    # Input
    url: str
    sample_url: Optional[str] = None
    
    # Bot protection
    bot_protection: BotProtectionInfo
    
    # JavaScript detection
    javascript_required: bool = False
    js_indicators: List[str] = Field(default_factory=list)
    
    # Content analysis
    html_size_bytes: Optional[int] = None
    has_meaningful_content: bool = False
    content_preview: Optional[str] = None
    
    # Crawler test (if available)
    crawler_test_success: Optional[bool] = None
    crawler_test_error: Optional[str] = None
    
    # Issues found
    issues: List[PreflightIssue] = Field(default_factory=list)
    
    # Firecrawl recommendation
    firecrawl: FirecrawlRecommendation
    
    # Overall
    viable_for_open_crawler: bool = False
    check_duration_ms: int = 0


# =============================================================================
# Helper Functions
# =============================================================================

def normalize_url(url: str) -> tuple[str, str, bool]:
    """
    Normalize URL and extract domain.
    
    Returns: (normalized_url, domain, is_valid)
    """
    url = url.strip()
    
    # Add scheme if missing
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return url, "", False
        
        domain = parsed.netloc.lower()
        # Remove www. prefix for consistency
        if domain.startswith("www."):
            domain = domain[4:]
        
        # Rebuild normalized URL
        normalized = f"{parsed.scheme}://{parsed.netloc}"
        if parsed.path and parsed.path != "/":
            normalized += parsed.path.rstrip("/")
        
        return normalized, domain, True
        
    except Exception:
        return url, "", False


async def check_dns(domain: str, timeout: float = 5.0) -> tuple[bool, Optional[str]]:
    """
    Check if domain resolves via DNS.
    
    Returns: (resolves, error_message)
    """
    try:
        loop = asyncio.get_event_loop()
        await asyncio.wait_for(
            loop.run_in_executor(None, socket.gethostbyname, domain),
            timeout=timeout
        )
        return True, None
    except socket.gaierror as e:
        return False, f"DNS resolution failed: {e}"
    except asyncio.TimeoutError:
        return False, "DNS resolution timed out"
    except Exception as e:
        return False, f"DNS check error: {e}"


async def fetch_url(
    url: str, 
    timeout: float = 10.0,
    follow_redirects: bool = True,
) -> tuple[Optional[httpx.Response], List[str], Optional[str]]:
    """
    Fetch URL and track redirects.
    
    Returns: (response, redirect_chain, error_message)
    """
    redirect_chain = []
    
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=follow_redirects,
            verify=True,
        ) as client:
            response = await client.get(url)
            
            # Track redirect history
            if response.history:
                redirect_chain = [str(r.url) for r in response.history]
            
            return response, redirect_chain, None
            
    except httpx.TimeoutException:
        return None, redirect_chain, "Request timed out"
    except httpx.ConnectError as e:
        return None, redirect_chain, f"Connection failed: {e}"
    except httpx.TooManyRedirects:
        return None, redirect_chain, "Too many redirects"
    except Exception as e:
        return None, redirect_chain, f"Request error: {e}"


def parse_robots_txt(content: str, user_agent: str = "*") -> RobotsTxtInfo:
    """
    Parse robots.txt content.
    
    Properly handles multiple User-agent sections by only applying rules
    from the wildcard (*) section to our crawler.
    """
    info = RobotsTxtInfo(exists=True, raw_content=content[:2000])
    
    # Track which user-agent section we're in
    in_wildcard_section = False
    seen_wildcard = False
    
    for raw_line in content.split("\n"):
        # Preserve original line for URLs, use lowercase for directives
        line_stripped = raw_line.strip()
        line_lower = line_stripped.lower()
        
        if not line_stripped or line_lower.startswith("#"):
            continue
        
        # User-agent directive starts a new section
        if line_lower.startswith("user-agent:"):
            agent = line_lower.split(":", 1)[1].strip()
            # Only apply rules from the wildcard (*) section
            # Other specific user-agents (Googlebot, etc.) don't apply to us
            if agent == "*":
                in_wildcard_section = True
                seen_wildcard = True
            else:
                in_wildcard_section = False
        
        # Sitemap directives are global (apply regardless of user-agent)
        elif line_lower.startswith("sitemap:"):
            # Use original line to preserve URL case
            sitemap = line_stripped.split(":", 1)[1].strip()
            # Handle sitemap: https://... (colon in URL)
            if "://" not in sitemap and len(line_stripped.split(":")) > 2:
                # Reconstruct URL: sitemap:https://example.com
                parts = line_stripped.split(":", 2)
                sitemap = parts[1].strip() + ":" + parts[2]
            if sitemap and sitemap not in info.sitemap_urls:
                info.sitemap_urls.append(sitemap)
        
        # Disallow/Allow/Crawl-delay only apply within our section
        elif in_wildcard_section:
            if line_lower.startswith("disallow:"):
                path = line_lower.split(":", 1)[1].strip()
                if path and path not in info.blocked_paths:
                    info.blocked_paths.append(path)
                    if path == "/":
                        info.allows_crawling = False
                        
            elif line_lower.startswith("crawl-delay:"):
                try:
                    info.crawl_delay = int(line_lower.split(":", 1)[1].strip())
                except ValueError:
                    pass
    
    # If we never saw a wildcard section, assume crawling is allowed
    if not seen_wildcard:
        info.allows_crawling = True
    
    return info


def detect_bot_protection(
    response: httpx.Response,
    html_content: str,
) -> BotProtectionInfo:
    """Detect bot protection from response."""
    info = BotProtectionInfo()
    headers_lower = {k.lower(): v for k, v in response.headers.items()}
    html_lower = html_content.lower()
    
    for provider_id, signatures in BOT_PROTECTION_SIGNATURES.items():
        # Check headers
        for header in signatures["headers"]:
            if header.lower() in headers_lower:
                info.indicators.append(f"Header: {header}")
        
        # Check body patterns
        for pattern in signatures["body_patterns"]:
            if re.search(pattern, html_lower, re.IGNORECASE):
                info.indicators.append(f"Body pattern: {pattern}")
        
        # If we found indicators for this provider
        if info.indicators:
            info.detected = True
            info.provider = provider_id
            info.provider_name = signatures["name"]
            break
    
    # Set confidence based on indicator count
    if len(info.indicators) >= 3:
        info.confidence = "high"
    elif len(info.indicators) >= 2:
        info.confidence = "medium"
    elif len(info.indicators) >= 1:
        info.confidence = "low"
    
    # Check for challenge pages
    challenge_patterns = [
        r"checking your browser",
        r"please wait",
        r"verify you are human",
        r"just a moment",
        r"ddos protection",
    ]
    for pattern in challenge_patterns:
        if re.search(pattern, html_lower):
            info.detected = True
            info.confidence = "high"
            info.indicators.append(f"Challenge page: {pattern}")
            if not info.provider_name:
                info.provider_name = "Unknown Bot Protection"
    
    return info


def detect_javascript_required(html_content: str) -> tuple[bool, List[str]]:
    """Detect if site requires JavaScript."""
    indicators = []
    html_lower = html_content.lower()
    
    for pattern in JS_REQUIRED_PATTERNS:
        if re.search(pattern, html_lower, re.IGNORECASE | re.DOTALL):
            indicators.append(pattern)
    
    # Check for minimal HTML body (JS-rendered SPA)
    body_match = re.search(r"<body[^>]*>(.*?)</body>", html_content, re.DOTALL | re.IGNORECASE)
    if body_match:
        body_content = body_match.group(1).strip()
        # Remove script tags and check what's left
        body_no_scripts = re.sub(r"<script[^>]*>.*?</script>", "", body_content, flags=re.DOTALL | re.IGNORECASE)
        body_no_scripts = re.sub(r"<[^>]+>", "", body_no_scripts).strip()
        
        if len(body_no_scripts) < 100:
            indicators.append("Minimal HTML body content (likely JS-rendered)")
    
    return len(indicators) > 0, indicators


def build_firecrawl_recommendation(
    bot_protection: BotProtectionInfo,
    js_required: bool,
    crawler_blocked: bool = False,
) -> FirecrawlRecommendation:
    """Build Firecrawl recommendation based on issues."""
    rec = FirecrawlRecommendation(when_to_use=FIRECRAWL_INFO["when_to_use"])
    
    reasons = []
    
    if bot_protection.detected:
        reasons.append(f"{bot_protection.provider_name or 'Bot protection'} detected")
        rec.recommended = True
    
    if js_required:
        reasons.append("Site requires JavaScript rendering")
        rec.recommended = True
    
    if crawler_blocked:
        reasons.append("Open Crawler was blocked during test")
        rec.recommended = True
    
    if rec.recommended and reasons:
        rec.reason = "; ".join(reasons)
    
    return rec


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/preflight", response_model=PreflightResponse)
async def domain_preflight(request: PreflightRequest) -> PreflightResponse:
    """
    Fast preflight checks for a domain (~2-3 seconds).
    
    Checks:
    - URL format validation
    - DNS resolution
    - HTTP connectivity
    - HTTPS availability
    - robots.txt (if enabled)
    
    Use this for debounced validation as user types.
    No LLM or crawler required.
    """
    start_time = time.time()
    
    # Normalize URL
    normalized_url, domain, url_valid = normalize_url(request.url)
    
    response = PreflightResponse(
        original_url=request.url,
        normalized_url=normalized_url,
        domain=domain,
        url_valid=url_valid,
    )
    
    if not url_valid:
        response.issues.append(PreflightIssue(
            severity=IssueSeverity.ERROR,
            code="INVALID_URL",
            message="URL format is invalid",
            suggestion="Enter a valid URL starting with http:// or https://",
        ))
        return response
    
    # DNS check
    dns_ok, dns_error = await check_dns(domain)
    response.dns_resolves = dns_ok
    
    if not dns_ok:
        response.issues.append(PreflightIssue(
            severity=IssueSeverity.ERROR,
            code="DNS_FAILURE",
            message=dns_error or "Domain does not resolve",
            suggestion="Check the domain spelling or try again later",
        ))
        return response
    
    # HTTP connectivity check
    fetch_start = time.time()
    http_response, redirect_chain, http_error = await fetch_url(normalized_url)
    
    if http_response:
        response.http_reachable = True
        response.status_code = http_response.status_code
        response.final_url = str(http_response.url)
        response.redirect_chain = redirect_chain
        response.response_time_ms = int((time.time() - fetch_start) * 1000)
        response.https_available = str(http_response.url).startswith("https://")
        
        # Check for error status codes
        if http_response.status_code >= 400:
            severity = IssueSeverity.ERROR if http_response.status_code >= 500 else IssueSeverity.WARNING
            response.issues.append(PreflightIssue(
                severity=severity,
                code=f"HTTP_{http_response.status_code}",
                message=f"Site returned HTTP {http_response.status_code}",
                suggestion="The site may be down or blocking requests",
            ))
    else:
        response.issues.append(PreflightIssue(
            severity=IssueSeverity.ERROR,
            code="HTTP_UNREACHABLE",
            message=http_error or "Could not reach the site",
            suggestion="Check if the site is accessible in your browser",
        ))
        return response
    
    # robots.txt check - always at domain root, not relative to path
    if request.check_robots:
        parsed = urlparse(normalized_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        robots_response, _, _ = await fetch_url(robots_url, timeout=5.0)
        
        if robots_response and robots_response.status_code == 200:
            robots_content = robots_response.text
            response.robots_txt = parse_robots_txt(robots_content)
            
            if not response.robots_txt.allows_crawling:
                response.issues.append(PreflightIssue(
                    severity=IssueSeverity.WARNING,
                    code="ROBOTS_DISALLOW_ALL",
                    message="robots.txt disallows all crawling",
                    suggestion="The site may not want to be crawled. Check their terms of service.",
                    details={"blocked_paths": response.robots_txt.blocked_paths},
                ))
            elif response.robots_txt.blocked_paths:
                response.issues.append(PreflightIssue(
                    severity=IssueSeverity.INFO,
                    code="ROBOTS_PARTIAL_BLOCK",
                    message=f"robots.txt blocks {len(response.robots_txt.blocked_paths)} paths",
                    details={"blocked_paths": response.robots_txt.blocked_paths[:10]},
                ))
            
            if response.robots_txt.crawl_delay and response.robots_txt.crawl_delay > 5:
                response.issues.append(PreflightIssue(
                    severity=IssueSeverity.WARNING,
                    code="SLOW_CRAWL_DELAY",
                    message=f"robots.txt requests {response.robots_txt.crawl_delay}s crawl delay",
                    suggestion="Crawling will be slow. Consider if this is acceptable.",
                ))
        else:
            response.robots_txt = RobotsTxtInfo(exists=False)
    
    # Determine overall viability
    has_errors = any(i.severity == IssueSeverity.ERROR for i in response.issues)
    response.viable_for_crawling = response.http_reachable and not has_errors
    
    return response


@router.post("/deep-check", response_model=DeepCheckResponse)
async def domain_deep_check(request: DeepCheckRequest) -> DeepCheckResponse:
    """
    Thorough checks for a domain (~5-10 seconds).
    
    Checks:
    - Bot protection detection (Cloudflare, Akamai, etc.)
    - JavaScript rendering requirements
    - Content analysis
    - Open Crawler urltest (if available)
    
    Provides Firecrawl recommendation if issues detected.
    
    This should run before engaging the LLM workflow.
    """
    start_time = time.time()
    
    # Normalize URL
    normalized_url, domain, _ = normalize_url(request.url)
    sample_url = request.sample_path
    if sample_url and not sample_url.startswith("http"):
        sample_url = f"{normalized_url.rstrip('/')}/{sample_url.lstrip('/')}"
    
    response = DeepCheckResponse(
        url=normalized_url,
        sample_url=sample_url,
        bot_protection=BotProtectionInfo(),
        firecrawl=FirecrawlRecommendation(when_to_use=FIRECRAWL_INFO["when_to_use"]),
    )
    
    # Fetch page for analysis
    test_url = sample_url or normalized_url
    http_response, _, http_error = await fetch_url(test_url, timeout=15.0)
    
    if not http_response:
        response.issues.append(PreflightIssue(
            severity=IssueSeverity.ERROR,
            code="FETCH_FAILED",
            message=http_error or "Could not fetch page",
        ))
        response.check_duration_ms = int((time.time() - start_time) * 1000)
        return response
    
    html_content = http_response.text
    response.html_size_bytes = len(html_content.encode('utf-8'))
    
    # Bot protection detection
    response.bot_protection = detect_bot_protection(http_response, html_content)
    
    if response.bot_protection.detected:
        response.issues.append(PreflightIssue(
            severity=IssueSeverity.WARNING,
            code="BOT_PROTECTION",
            message=f"{response.bot_protection.provider_name} detected",
            suggestion="Open Crawler may be blocked. Consider using Firecrawl.",
            details={"indicators": response.bot_protection.indicators[:5]},
        ))
    
    # JavaScript detection
    response.javascript_required, response.js_indicators = detect_javascript_required(html_content)
    
    if response.javascript_required:
        response.issues.append(PreflightIssue(
            severity=IssueSeverity.WARNING,
            code="JAVASCRIPT_REQUIRED",
            message="Site appears to require JavaScript rendering",
            suggestion="Open Crawler has limited JS support. Consider using Firecrawl.",
            details={"indicators": response.js_indicators[:3]},
        ))
    
    # Content analysis
    # Strip HTML tags and check for meaningful content
    text_content = re.sub(r'<[^>]+>', '', html_content)
    text_content = re.sub(r'\s+', ' ', text_content).strip()
    response.has_meaningful_content = len(text_content) > 500
    response.content_preview = text_content[:200] if text_content else None
    
    if not response.has_meaningful_content:
        response.issues.append(PreflightIssue(
            severity=IssueSeverity.WARNING,
            code="MINIMAL_CONTENT",
            message="Page has minimal text content",
            suggestion="Content may be loaded via JavaScript after page load",
        ))
    
    # Try Open Crawler urltest to verify the site is actually crawlable
    # This takes ~5 seconds but gives us a definitive answer vs. guessing with heuristics
    crawler_client = get_crawler_client()
    if crawler_client.is_available():
        logger.info("Testing crawlability with Open Crawler", url=test_url)
        try:
            # Create minimal config for urltest
            # Domain URL must not have a path - extract just scheme://netloc
            parsed = urlparse(normalized_url)
            domain_root = f"{parsed.scheme}://{parsed.netloc}"
            
            minimal_config = {
                "domains": [{"url": domain_root}],
                "output_sink": "console",
            }
            
            # Wrap in timeout to prevent blocking the entire deep check
            urltest_result = await asyncio.wait_for(
                crawler_client.urltest(minimal_config, test_url),
                timeout=35.0  # Slightly longer than the internal 30s timeout
            )
            # For crawlability testing, we consider it a success if:
            # 1. The command succeeded (return_code 0)
            # 2. The site didn't block us
            # Even if no document was extracted (because we have no extraction rules), 
            # that's fine - we just want to know if the page is accessible
            page_accessible = (
                urltest_result.return_code == 0 and 
                not urltest_result.blocked
            )
            
            # "No document extracted" means page was fetched but no extraction rules matched
            # This is expected since our test config has no extraction rules - it's still a pass
            no_extraction_rules_error = (
                urltest_result.error and 
                "no document extracted" in urltest_result.error.lower()
            )
            
            response.crawler_test_success = page_accessible
            
            if page_accessible:
                if no_extraction_rules_error:
                    logger.info("Crawler test passed (page accessible, no extraction rules)", url=test_url)
                    response.issues.append(PreflightIssue(
                        severity=IssueSeverity.INFO,
                        code="CRAWLER_TEST_PASSED",
                        message="Open Crawler successfully accessed the page",
                        suggestion="The site is confirmed crawlable with Open Crawler.",
                    ))
                else:
                    logger.info("Crawler test passed", url=test_url)
                    response.issues.append(PreflightIssue(
                        severity=IssueSeverity.INFO,
                        code="CRAWLER_TEST_PASSED",
                        message="Open Crawler successfully fetched the page",
                        suggestion="The site is confirmed crawlable with Open Crawler.",
                    ))
            else:
                response.crawler_test_error = urltest_result.error
                logger.warning("Crawler test failed", url=test_url, error=urltest_result.error, blocked=urltest_result.blocked)
                
                if urltest_result.blocked:
                    response.issues.append(PreflightIssue(
                        severity=IssueSeverity.ERROR,
                        code="CRAWLER_BLOCKED",
                        message=f"Open Crawler was blocked: {urltest_result.block_reason or 'Access denied'}",
                        suggestion="This site actively blocks crawlers. Consider using Firecrawl instead.",
                    ))
                else:
                    response.issues.append(PreflightIssue(
                        severity=IssueSeverity.WARNING,
                        code="CRAWLER_TEST_FAILED",
                        message=f"Crawler test failed: {urltest_result.error or 'Unknown error'}",
                        suggestion="The crawler couldn't fetch this page. Check if the URL is correct.",
                    ))
        except asyncio.TimeoutError:
            response.crawler_test_error = "Crawler test timed out after 35s"
            logger.warning("Crawler test timed out", url=test_url)
            response.issues.append(PreflightIssue(
                severity=IssueSeverity.WARNING,
                code="CRAWLER_TIMEOUT",
                message="Crawler test timed out (35s)",
                suggestion="The site may be slow or the crawler is overloaded. Proceeding with heuristics.",
            ))
        except Exception as e:
            response.crawler_test_error = str(e)
            logger.error("Crawler test error", url=test_url, error=str(e))
            response.issues.append(PreflightIssue(
                severity=IssueSeverity.WARNING,
                code="CRAWLER_ERROR",
                message=f"Crawler test error: {str(e)}",
                suggestion="Could not run crawler test. Proceeding with heuristics.",
            ))
    else:
        logger.debug("Crawler binary not available, using heuristics only")
        response.issues.append(PreflightIssue(
            severity=IssueSeverity.INFO,
            code="CRAWLER_UNAVAILABLE",
            message="Open Crawler binary not available for testing",
            suggestion="Crawlability determined by heuristics (bot protection, JS detection).",
        ))
    
    # Build Firecrawl recommendation
    crawler_blocked = (
        response.crawler_test_success is False and 
        response.crawler_test_error and 
        "blocked" in response.crawler_test_error.lower()
    )
    response.firecrawl = build_firecrawl_recommendation(
        response.bot_protection,
        response.javascript_required,
        crawler_blocked,
    )
    
    # Determine viability for Open Crawler
    # Trust the actual crawler test result over heuristics:
    # - If crawler test succeeded, the site is viable regardless of JS detection
    # - If crawler test failed/blocked, the site is not viable
    # - If no crawler test, fall back to heuristics
    if response.crawler_test_success is True:
        # Actual test succeeded - site is viable even if it has JS features
        response.viable_for_open_crawler = True
    elif response.crawler_test_success is False:
        # Actual test failed - site is not viable
        response.viable_for_open_crawler = False
    else:
        # No crawler test - use heuristics
        # Only block on HIGH confidence bot protection (challenge pages, CAPTCHAs)
        has_blocking_issues = (
            response.bot_protection.confidence == "high" or
            crawler_blocked
        )
        # JS detection is just a warning, not a blocker when crawler unavailable
        response.viable_for_open_crawler = not has_blocking_issues
    
    response.check_duration_ms = int((time.time() - start_time) * 1000)
    
    return response


@router.get("/firecrawl-info")
async def get_firecrawl_info():
    """
    Get information about Firecrawl as an alternative.
    
    Returns pricing info and when to use Firecrawl.
    """
    return FIRECRAWL_INFO
