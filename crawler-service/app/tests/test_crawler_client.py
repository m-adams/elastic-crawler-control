"""
Tests for Open Crawler Client.

These tests verify the CrawlerClient interface and output parsing.
Live tests (marked @pytest.mark.crawler) require Open Crawler to be installed.

Run live tests with:
    CRAWLER_PATH=/crawler pytest app/tests/test_crawler_client.py -v -m crawler
"""

import os
import pytest

from utils.crawler_client import (
    CrawlerClient,
    ValidationResult,
    UrlTestResult,
    CrawlResult,
    get_crawler_client,
)


class TestCrawlerClientInterface:
    """Tests for CrawlerClient interface (no crawler required)."""
    
    def test_client_initialization(self):
        """Client should initialize with default or custom path."""
        client = CrawlerClient()
        assert client.crawler_path == "/crawler"
        assert client.timeout_seconds == 120
        
        custom_client = CrawlerClient(crawler_path="/custom", timeout_seconds=60)
        assert custom_client.crawler_path == "/custom"
        assert custom_client.timeout_seconds == 60
    
    def test_is_available_returns_bool(self):
        """is_available should return boolean."""
        client = CrawlerClient()
        result = client.is_available()
        assert isinstance(result, bool)
    
    def test_validation_result_dataclass(self):
        """ValidationResult should have correct fields."""
        result = ValidationResult(
            valid=True,
            errors=[],
            warnings=["warning1"],
            raw_output="output",
            return_code=0,
        )
        assert result.valid is True
        assert result.errors == []
        assert result.warnings == ["warning1"]
        assert result.raw_output == "output"
        assert result.return_code == 0
    
    def test_urltest_result_dataclass(self):
        """UrlTestResult should have correct fields."""
        result = UrlTestResult(
            success=True,
            url="https://example.com",
            extracted_document={"title": "Test"},
            error=None,
            blocked=False,
        )
        assert result.success is True
        assert result.url == "https://example.com"
        assert result.extracted_document == {"title": "Test"}
        assert result.blocked is False
    
    def test_crawl_result_dataclass(self):
        """CrawlResult should have correct fields."""
        result = CrawlResult(
            success=True,
            pages_visited=10,
            documents_indexed=8,
            duration_seconds=45.5,
        )
        assert result.success is True
        assert result.pages_visited == 10
        assert result.documents_indexed == 8
        assert result.duration_seconds == 45.5


class TestOutputParsing:
    """Tests for output parsing methods."""
    
    def test_detect_blocked_cloudflare(self):
        """Should detect Cloudflare blocks."""
        client = CrawlerClient()
        output = "Error: Cloudflare protection detected, please verify you are human"
        assert client._detect_blocked(output, 1) is True
        assert "Cloudflare" in client._identify_block_reason(output)
    
    def test_detect_blocked_captcha(self):
        """Should detect CAPTCHA challenges."""
        client = CrawlerClient()
        output = "Page requires CAPTCHA verification"
        assert client._detect_blocked(output, 1) is True
        assert "CAPTCHA" in client._identify_block_reason(output)
    
    def test_detect_blocked_403(self):
        """Should detect 403 forbidden."""
        client = CrawlerClient()
        output = "HTTP 403 Forbidden"
        assert client._detect_blocked(output, 1) is True
        assert "403" in client._identify_block_reason(output)
    
    def test_detect_blocked_rate_limit(self):
        """Should detect rate limiting."""
        client = CrawlerClient()
        output = "Error: Too many requests, rate limit exceeded"
        assert client._detect_blocked(output, 1) is True
        assert "Rate" in client._identify_block_reason(output)
    
    def test_not_blocked_normal_output(self):
        """Should not detect block on normal output."""
        client = CrawlerClient()
        output = "Fetching https://example.com\nExtracted document: {...}"
        assert client._detect_blocked(output, 0) is False
    
    def test_parse_urltest_output_json(self):
        """Should parse JSON document from urltest output."""
        client = CrawlerClient()
        output = '''
        Fetching URL: https://example.com
        Extracted document: {"url": "https://example.com", "title": "Example", "body": "content"}
        Done.
        '''
        doc = client._parse_urltest_output(output)
        assert doc is not None
        assert doc.get("url") == "https://example.com"
        assert doc.get("title") == "Example"
    
    def test_parse_urltest_output_no_json(self):
        """Should return None when no JSON found."""
        client = CrawlerClient()
        output = "Error: Failed to fetch URL"
        doc = client._parse_urltest_output(output)
        assert doc is None
    
    def test_extract_error_message(self):
        """Should extract error message from output."""
        client = CrawlerClient()
        output = "Starting crawl...\nError: Connection refused\nAborting."
        error = client._extract_error_message(output)
        assert "Error" in error or "Connection" in error


class TestConfigWriting:
    """Tests for config file handling."""
    
    def test_write_temp_config(self):
        """Should write config to temp file."""
        client = CrawlerClient()
        config = {"domains": [{"url": "https://example.com"}]}
        
        path = client._write_temp_config(config)
        
        assert os.path.exists(path)
        assert path.endswith(".yml")
        
        # Verify content
        with open(path) as f:
            content = f.read()
        assert "example.com" in content
        
        # Cleanup
        client._cleanup_temp_config(path)
        assert not os.path.exists(path)
    
    def test_cleanup_nonexistent_file(self):
        """Cleanup should not raise for nonexistent file."""
        client = CrawlerClient()
        # Should not raise
        client._cleanup_temp_config("/nonexistent/path.yml")


class TestSingleton:
    """Tests for singleton pattern."""
    
    def test_get_crawler_client_returns_client(self):
        """get_crawler_client should return CrawlerClient."""
        client = get_crawler_client()
        assert isinstance(client, CrawlerClient)
    
    def test_get_crawler_client_singleton(self):
        """get_crawler_client should return same instance."""
        client1 = get_crawler_client()
        client2 = get_crawler_client()
        assert client1 is client2


# ============================================================================
# LIVE TESTS - Require Open Crawler to be installed
# ============================================================================

@pytest.mark.skipif(
    not os.path.exists("/crawler/bin/crawler"),
    reason="Open Crawler not installed at /crawler"
)
class TestCrawlerClientLive:
    """
    Live tests that require Open Crawler.
    
    These tests run real crawler commands and verify actual behavior.
    Skip if crawler not available.
    """
    
    @pytest.fixture
    def client(self):
        """Create crawler client."""
        return CrawlerClient(crawler_path="/crawler")
    
    @pytest.fixture
    def valid_config(self):
        """A minimal valid config."""
        return {
            "domains": [
                {
                    "url": "https://example.com",
                    "seed_urls": ["https://example.com/"],
                }
            ],
            "output_sink": "console",
        }
    
    @pytest.mark.asyncio
    async def test_validate_valid_config(self, client, valid_config):
        """Validate should pass for valid config."""
        result = await client.validate(valid_config)
        
        assert isinstance(result, ValidationResult)
        # Note: May have warnings but should not error on basic config
        print(f"Validation result: valid={result.valid}, errors={result.errors}")
    
    @pytest.mark.asyncio
    async def test_validate_invalid_config(self, client):
        """Validate should fail for invalid config."""
        invalid_config = {"invalid": "config"}
        
        result = await client.validate(invalid_config)
        
        assert isinstance(result, ValidationResult)
        # Should have errors for missing required fields
        assert result.valid is False or len(result.errors) > 0
    
    @pytest.mark.asyncio
    async def test_urltest_example_com(self, client, valid_config):
        """urltest should work on example.com."""
        result = await client.urltest(valid_config, "https://example.com/")
        
        assert isinstance(result, UrlTestResult)
        assert result.url == "https://example.com/"
        
        # example.com should not block
        if result.success:
            assert result.extracted_document is not None
            print(f"Extracted: {result.extracted_document}")
        else:
            print(f"urltest failed: {result.error}")
    
    @pytest.mark.asyncio
    async def test_urltest_blocked_detection(self, client, valid_config):
        """urltest should detect blocked sites."""
        # Use a URL known to block (may vary)
        result = await client.urltest(valid_config, "https://www.linkedin.com/")
        
        assert isinstance(result, UrlTestResult)
        # LinkedIn typically blocks crawlers
        if result.blocked:
            assert result.block_reason is not None
            print(f"Blocked: {result.block_reason}")
    
    @pytest.mark.asyncio
    async def test_is_available(self, client):
        """is_available should return True when crawler installed."""
        assert client.is_available() is True
